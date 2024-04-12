from io import TextIOWrapper
import os
from xml.etree import ElementTree as ET

xml_prefix = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://raw.githubusercontent.com/acdh-oeaw/apis-oebl-export/main/oebl_relax_ng_v1.rng" type="application/xml" 
schematypens="http://relaxng.org/ns/structure/1.0"?>
"""


def parse_hmi_file(file_path: str) -> dict:
    with open(file_path, "r") as file:
        lines = file.readlines()

    data = {}
    for line in lines:
        if "=" in line:
            key, value = line.strip().split("=", 1)
            data[key] = value

    return data


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
    return xml_file


def create_harmonized_xmls(verlag_folder: str, output_folder: str):
    """Run through the folder of XMLs and enrich them with information
    from the HMI file. Save the enriched XMLs in the output folder."""

    # Iterate over all subdirectories
    for subdir, dirs, files in os.walk(verlag_folder):
        for file in files:
            # Check if the file is an XML file
            if file.endswith(".xml"):
                file_path = os.path.join(subdir, file)
                with open(file_path, "r") as xml_file:
                    # Process the XML file here
                    tree = ET.parse(xml_file)
                    hmi_file = parse_hmi_file(file_path + ".hmi")
                    xml_neu = enrich_verlag_xml(tree, hmi_file)
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
