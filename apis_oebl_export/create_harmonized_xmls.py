from io import TextIOWrapper
import logging
import os
from xml.etree import ElementTree as ET

# xml_prefix = """<?xml version="1.0" encoding="UTF-8"?>
# <?xml-model href="https://raw.githubusercontent.com/acdh-oeaw/apis-oebl-export/main/oebl_relax_ng_v1.rng" type="application/xml"
# schematypens="http://relaxng.org/ns/structure/1.0"?>
# """
xml_prefix = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="/workspaces/oebl-apis-rdf/apis-oebl-export/oebl_relax_ng_v1.rng" type="application/xml" 
schematypens="http://relaxng.org/ns/structure/1.0"?>
"""
oebl_ns = {"oebl": "http://www.biographien.ac.at"}
logger = logging.getLogger(__name__)


def parse_hmi_file(file_path: str) -> dict:
    with open(file_path, "r") as file:
        lines = file.readlines()

    data = {}
    for line in lines:
        if "=" in line:
            key, value = line.strip().split("=", 1)
            data[key] = value

    return data


def remove_namespace(doc, namespace):
    """Remove namespace in the passed document in place."""
    ns = f"{namespace}"
    nsl = len(ns)
    for elem in doc.iter():
        if elem.tag.startswith(ns):
            elem.tag = elem.tag[nsl:]


def get_data_from_gideon_files(xml_file_name: str, dirs: list) -> dict:
    data = {
        "PubInfo": None,
        "Geburt": None,
        "Tod": None,
    }
    for directory in dirs:
        for subdir, dirs, files in os.walk(directory[0]):
            for file in files:
                if file == xml_file_name.split(".")[0] + directory[1]:
                    file_path = os.path.join(subdir, file)
                    tree = ET.parse(file_path)
                    remove_namespace(tree, "{http://www.biographien.ac.at}")
                    root = tree.getroot()

                    pub_info = root.find(".//PubInfo")
                    geburt = root.find(".//Geburt")
                    tod = root.find(".//Tod")
                    data = {
                        "PubInfo": pub_info,
                        "Geburt": geburt,
                        "Tod": tod,
                    }
    return data


def copy_print_version(
    xml_file_name: str,
    dirs: list,
    hmi_file: dict,
    target_folder: str = "/workspaces/oebl-apis-rdf/oebl-harmonized-neu/",
) -> str:
    file_check = False
    for directory in dirs:
        for subdir, dirs, files in os.walk(directory):
            for file in files:
                if file == xml_file_name + ".xml":
                    file_check = True
                    file_path = os.path.join(subdir, file)
                    tree = ET.parse(file_path)
                    remove_namespace(tree, "{http://www.biographien.ac.at}")
                    x_root = tree.getroot()
                    x_root.set(
                        "Nummer", x_root.get("Nummer").replace(".xml", "_print.xml")
                    )
                    x_root.set("new_version", xml_file_name + ".xml")
                    if "doi" in hmi_file:
                        x_root.set("doi", hmi_file["doi"])
                    if "oebl_id" in hmi_file:
                        x_root.set("oebl_id", hmi_file["oebl_id"])
                    if "vaw_PND" in hmi_file:
                        x_root.set("gnd", hmi_file["vaw_PND"])
                    if "oebl_Geschlecht" in hmi_file:
                        x_root.find("Lexikonartikel").append(ET.Element("Geschlecht"))
                        x_root.find("Lexikonartikel/Geschlecht").set(
                            "Type", hmi_file["oebl_Geschlecht"]
                        )
                    if "oebl_Biographie" in hmi_file:
                        x_root.set("pdf_file", hmi_file["oebl_Biographie"])
                    for elem in x_root.find(".//Nebenbezeichnung"):
                        if "type" in elem.attrib:
                            elem.set("Type", "Vorname")
                            elem.attrib.pop("type")
                    for elem in x_root.find(".//Lieferung"):
                        elem.tag = "PubInfo"
                    new_file_path = os.path.join(
                        target_folder + xml_file_name + "_print.xml"
                    )
                    tree.write(new_file_path)
                    with open(new_file_path, "r+") as f:
                        content = f.read()
                        f.seek(0, 0)
                        f.write(xml_prefix + content)
    if not file_check:
        logger.warning(f"No print version found for {xml_file_name}")


def enrich_verlag_xml(xml_file: ET, hmi_file: dict):
    """Enrich the XML file with information from the HMI file."""
    x_root = xml_file.getroot()
    if "doi" in hmi_file:
        x_root.set("doi", hmi_file["doi"])
    if "oebl_id" in hmi_file:
        x_root.set("oebl_id", hmi_file["oebl_id"])
    if "vaw_PND" in hmi_file:
        x_root.set("gnd", hmi_file["vaw_PND"])
    if "oebl_Geschlecht" in hmi_file:
        x_root.find("Lexikonartikel").append(ET.Element("Geschlecht"))
        x_root.find("Lexikonartikel/Geschlecht").set(
            "Type", hmi_file["oebl_Geschlecht"]
        )
    if "oebl_Biographie" in hmi_file:
        x_root.set("pdf_file", hmi_file["oebl_Biographie"])
    x_root.find(".//Hauptbezeichnung").text = (
        x_root.find(".//Hauptbezeichnung").text.strip().strip(",")
    )
    try:
        x_root.find(".//Nebenbezeichnung").set(
            "Type", x_root.find(".//Nebenbezeichnung").attrib.pop("type")
        )
    except KeyError:
        logger.warning("Vorname not found as type in Nebenbezeichnung")
        x_root.find(".//Nebenbezeichnung").set("Type", "Vorname")

    additional_data = get_data_from_gideon_files(
        x_root.get("Nummer"),
        [
            (
                "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_UND_Online",
                "_online.xml",
            ),
            ("/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_only", "_Reg.xml"),
            ("/workspaces/oebl-apis-rdf/oebl-xml-gideon/Online_only", ".xml"),
        ],
    )
    if additional_data["PubInfo"] is None:
        additional_data = get_data_from_gideon_files(
            x_root.get("Nummer"),
            [],
        )
    if len(x_root.findall(".//Lieferung")) == 2:
        copy_print_version(
            x_root.get("Nummer"),
            ["/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_UND_Online"],
            hmi_file,
        )
    if additional_data["PubInfo"] is not None:
        x_root.find(".//Lexikonartikel").append(additional_data["PubInfo"])
        x_root.find(".//Lexikonartikel").remove(x_root.find(".//Lieferung"))
    vita = x_root.find(".//Lexikonartikel/Vita")
    if additional_data["Geburt"] is not None:
        vita.remove(x_root.find(".//Geburt"))
        vita.append(additional_data["Geburt"])
    if additional_data["Tod"] is not None:
        vita.remove(x_root.find(".//Tod"))
        vita.append(additional_data["Tod"])
    return xml_file


def create_harmonized_xmls(verlag_folder: str, output_folder: str):
    """Run through the folder of XMLs and enrich them with information
    from the HMI file. Save the enriched XMLs in the output folder."""

    # Iterate over all subdirectories
    for subdir, dirs, files in os.walk(verlag_folder):
        for file in files:
            # leave out the 'verweise' for the moment
            if file.endswith("Verweis.xml"):
                logger.info(f"File is Verweis, skipping: {file}")
                continue
            # Check if the file is an XML file
            elif file.endswith(".xml"):
                file_path = os.path.join(subdir, file)
                logger.info(f"Processing file: {file_path}")
                output_file_path = os.path.join(output_folder, file)
                if os.path.exists(output_file_path):
                    logger.info(f"File already exists: {output_file_path}, skipping.")
                    continue
                with open(file_path, "r") as xml_file:
                    # Process the XML file here
                    try:
                        tree = ET.parse(xml_file)
                    except ET.ParseError:
                        logger.error(f"Error parsing file: {file_path}")
                        continue
                    if tree.getroot().get("Nummer") in [
                        "Koeroesy-Szanto_Josef_1844_1906.xml",
                        "Koszta_Jozsef_1861_1949.xml",
                    ]:
                        continue
                    hmi_file = parse_hmi_file(file_path + ".hmi")
                    xml_neu = enrich_verlag_xml(tree, hmi_file)
                    # Remove 'Lieferungen'  from XML
                    for lieferung in xml_neu.findall(".//Lieferung"):
                        xml_neu.find(".//Lexikonartikel").remove(lieferung)
                    # Save the enriched XML file
                    output_file = os.path.join(output_folder, file)
                    xml_neu.write(output_file)
                    with open(output_file, "r+") as f:
                        content = f.read()
                        f.seek(0, 0)
                        f.write(xml_prefix + content)


if __name__ == "__main__":
    create_harmonized_xmls(
        "/workspaces/oebl-apis-rdf/oebl-xml-verlag",
        "/workspaces/oebl-apis-rdf/oebl-harmonized-neu",
    )
