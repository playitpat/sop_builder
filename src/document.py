from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PLACEHOLDER="Click or tap here to enter text."
REQUIRED=["Document Control","Purpose","Scope","References and Terminology","Roles and Responsibilities","Process Flow","Procedure","Record of revisions","Appendices"]


def _plain(value):
    if value in (None,"",[]): return "TBD"
    if isinstance(value,list): return "\n".join(str(x) for x in value) or "None"
    if isinstance(value,dict): return "\n".join(f"{k}: {v}" for k,v in value.items()) or "TBD"
    return str(value)


def _replace_sdt(root,values):
    for sdt in root.findall(".//"+W+"sdt"):
        pr=sdt.find(W+"sdtPr"); tag=pr.find(W+"tag") if pr is not None else None
        name=tag.get(W+"val") if tag is not None else "ProcedureIntro"
        text=_plain(values.get(name,"TBD"))
        nodes=sdt.findall(".//"+W+"t")
        if nodes:
            nodes[0].text=text
            for n in nodes[1:]: n.text=""


def _replace_all(root,old,new):
    for node in root.findall(".//"+W+"t"):
        if node.text: node.text=node.text.replace(old,new)


def _replace_in_paragraphs(root, replacements):
    """Replace phrases split across Word runs while retaining the paragraph/container."""
    for paragraph in root.findall(".//"+W+"p"):
        nodes=paragraph.findall(".//"+W+"t")
        combined="".join(n.text or "" for n in nodes)
        changed=combined
        for old,new in replacements: changed=changed.replace(old,new)
        if nodes and changed != combined:
            nodes[0].text=changed
            for node in nodes[1:]: node.text=""


def populate_template(template: str|Path,draft: dict,output_dir: str|Path="generated") -> Path:
    template=Path(template); outdir=Path(output_dir); outdir.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r'[<>:"/\\|?*]+','-',draft["title"]).strip()
    output=outdir/f"SOP – {safe} – v{draft['version']}.docx"
    sections=draft["sections"]; roles=sections["Roles and Responsibilities"]
    dc=sections["Document Control"] if isinstance(sections["Document Control"],dict) else {}
    details="\n".join(f"{x['order']}. {x['role']}: {x['action']}" for x in sections["Procedure"]["Process details"]) or "TBD"
    values={"WriterName":dc.get("written_by","TBD"),"WrittenDate":dc.get("written_date","TBD"),"ValidatorName":dc.get("validated_by","TBD"),
            "ApproverName":dc.get("approved_by",roles["Accountable"]),"Purpose":sections["Purpose"],"InScope":sections["Scope"]["In-scope"],
            "OutScope":sections["Scope"]["Out-of-scope"],"References":sections["References and Terminology"],"RolesR":roles["Responsible"],
            "RolesA":roles["Accountable"],"RolesC":roles["Consulted"],"RolesI":roles["Informed"],"ProcessFlow":sections["Process Flow"],
            "ProcedureIntro":f"Trigger: {draft['trigger']}\nOutput: {draft['output']}\nApproval: {draft['approvals']}\nValidation: {draft['validation']}\nRecords: {draft['records']}",
            "GeneralConsiderations":sections["Procedure"]["General considerations"],"ProcessDetails":details,"Appendix":sections["Appendices"]}
    with ZipFile(template) as zin, ZipFile(output,"w",ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data=zin.read(info.filename)
            if info.filename=="word/document.xml":
                root=ET.fromstring(data); _replace_sdt(root,values)
                # Populate the existing revision row without rebuilding its table.
                texts=root.findall(".//"+W+"t")
                rev=False
                for n in texts:
                    if (n.text or "").strip()=="Record of revisions": rev=True
                    elif rev and (n.text or "").strip()=="1.0":
                        pass
                # Blank effective-date cell is immediately followed by New SOP in template; insert TBD in blank table cell.
                for row in root.findall(".//"+W+"tr"):
                    rowtext="|".join("".join(t.text or "" for t in cell.findall(".//"+W+"t")) for cell in row.findall(W+"tc"))
                    if rowtext.startswith("1.0|") and "New SOP" in rowtext:
                        cells=row.findall(W+"tc"); target=cells[1].find(".//"+W+"t")
                        if target is None:
                            p=cells[1].find(W+"p")
                            if p is None: p=ET.SubElement(cells[1],W+"p")
                            r=ET.SubElement(p,W+"r"); target=ET.SubElement(r,W+"t")
                        target.text=draft["effective_date"]
                data=ET.tostring(root,encoding="utf-8",xml_declaration=True)
            elif info.filename=="word/header1.xml":
                root=ET.fromstring(data)
                _replace_in_paragraphs(root,(("SOP-xxx",draft["qd_reference"]),("DD MM YYYY",draft["effective_date"]),("<TITLE>",draft["title"])))
                data=ET.tostring(root,encoding="utf-8",xml_declaration=True)
            zout.writestr(info,data)
    return output


def inspect_template(path):
    with ZipFile(path) as z:
        root=ET.fromstring(z.read("word/document.xml")); header=ET.fromstring(z.read("word/header1.xml")); footer=ET.fromstring(z.read("word/footer1.xml"))
        return {"parts":len(z.namelist()),"content_controls":len(root.findall(".//"+W+"sdt")),"tables":len(root.findall(".//"+W+"tbl")),
                "bookmarks":len(root.findall(".//"+W+"bookmarkStart")),"has_header":header is not None,"has_footer":footer is not None}


def validate_docx(path: str|Path) -> dict:
    errors=[]
    try:
        with ZipFile(path) as z:
            names=z.namelist(); root=ET.fromstring(z.read("word/document.xml")); header=ET.fromstring(z.read("word/header1.xml"))
            body="".join(n.text or "" for n in root.findall(".//"+W+"t")); head="".join(n.text or "" for n in header.findall(".//"+W+"t"))
            normalized=re.sub(r"\s+"," ",body)
            positions=[normalized.find(x) for x in REQUIRED]
            if any(x<0 for x in positions): errors.append("Required section missing")
            if positions != sorted(positions): errors.append("Required sections out of order")
            if PLACEHOLDER in body or "SOP-xxx" in head or "<TITLE>" in head or "DD MM YYYY" in head: errors.append("Unresolved template placeholder")
            if len(root.findall(".//"+W+"tbl"))<3: errors.append("Required template tables missing")
            if "1.0" not in body or "New SOP" not in body: errors.append("Revision entry missing")
            if "QD ref:" not in head or "Version: 1.0" not in head: errors.append("Header metadata missing")
            if not all(x in normalized for x in ("R Responsible","A Accountable")): errors.append("RACI table missing")
            if "word/styles.xml" not in names or "word/footer1.xml" not in names: errors.append("Template formatting parts missing")
    except (BadZipFile,KeyError,ET.ParseError) as exc: errors.append(f"DOCX cannot be opened: {exc}")
    return {"valid":not errors,"errors":errors}
