import argparse
import csv
from datetime import datetime
import logging
import os
import re
from typing import Literal
from lxml import etree as ET

# xml_prefix = """<?xml version="1.0" encoding="UTF-8"?>
# <?xml-model href="https://raw.githubusercontent.com/acdh-oeaw/apis-oebl-export/main/oebl_relax_ng_v1.rng" type="application/xml"
# schematypens="http://relaxng.org/ns/structure/1.0"?>
# """
xml_prefix = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="/workspaces/oebl-apis-rdf/apis-oebl-export/oebl_relax_ng_v1.rng" type="application/xml"
schematypens="http://relaxng.org/ns/structure/1.0"?>
"""
oebl_ns = {"oebl": "http://www.biographien.ac.at"}
logging.basicConfig(
    filename=f"create_harmonized_xmls_{datetime.now().strftime('%d-%m-%Y_%H:%M:%S')}.log",
    filemode="a",
    format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
count_print_only = 0
count_online_only = 0
count_print_and_online = 0
count_verweise = 0


def remove_tag_from_xml(xml_file: ET, tag: str) -> ET:
    """Remove a tag from the XML file."""
    for elem in xml_file.findall(f".//{tag}"):
        parent = elem.getparent()
        if elem.text:
            prev = elem.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + elem.text + (elem.tail or "")
            else:
                parent.text = (parent.text or "") + elem.text + (elem.tail or "")
        parent.remove(elem)
    return xml_file


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


def get_data_from_gideon_files(
    xml_file_name: str, gideon_index: dict, kind: Literal["online", "print"]
) -> dict:
    data = {
        "PubInfo": None,
        "Geburt": None,
        "Tod": None,
    }
    if xml_file_name in gideon_index:
        if kind in gideon_index[xml_file_name]:
            file_path = gideon_index[xml_file_name][kind]
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
    oebl_id: str,
    gideon_index: dict,
    hmi_file: dict,
    target_folder: str,
) -> str:
    file_path = None
    if "Adam_Heinrich" in xml_file_name:
        pass
    if oebl_id in gideon_index:
        if "print" in gideon_index[oebl_id]:
            file_path = gideon_index[oebl_id]["print"]
    elif xml_file_name in gideon_index:
        if "print" in gideon_index[xml_file_name]:
            file_path = gideon_index[xml_file_name]["print"]
    if file_path is None:
        if xml_file_name in gideon_index:
            if "print" in gideon_index[xml_file_name]:
                file_path = gideon_index[xml_file_name]["print"]
        if file_path is None:
            logger.warning(f"No print version found for {xml_file_name}")
            return False
    parser = ET.XMLParser(remove_comments=True, remove_pis=True)
    tree = ET.parse(file_path, parser)
    remove_namespace(tree, "{http://www.biographien.ac.at}")
    x_root = tree.getroot()
    x_root = remove_tag_from_xml(x_root, "Fett")
    x_root = remove_tag_from_xml(x_root, "Hoch")
    nummer = x_root.get("Nummer")
    if nummer is None:
        nummer = file_path.split("/")[-1].split(".")[0]
    nummer = nummer.replace(".xml", "")
    x_root.set("Nummer", nummer + "_print.xml")
    x_root.set("Version", "1")
    if "doi" in hmi_file:
        x_root.set("doi", hmi_file["doi"])
    if "eoebl_id" in hmi_file:
        x_root.set("eoebl_id", hmi_file["eoebl_id"])
    if "vaw_PND" in hmi_file:
        x_root.set("gnd", hmi_file["vaw_PND"])
    if "oebl_Geschlecht" in hmi_file:
        x_root.find("Lexikonartikel").append(ET.Element("Geschlecht"))
        x_root.find("Lexikonartikel/Geschlecht").set(
            "Type", hmi_file["oebl_Geschlecht"]
        )
    if "oebl_Biographie" in hmi_file:
        x_root.set("pdf_file", hmi_file["oebl_Biographie"])
    for elem in x_root.findall(".//Nebenbezeichnung"):
        if "type" in elem.attrib:
            elem.set("Type", elem.get("type"))
            elem.attrib.pop("type")
    for elem in x_root.findall(".//Lieferung"):
        elem.tag = "PubInfo"
    new_file_path = os.path.join(target_folder + "/" + nummer + "_print.xml")
    for att in x_root.attrib.keys():
        if att not in [
            "Nummer",
            "Version",
            "pnd",
            "eoebl_id",
            "doi",
            "gnd",
            "pdf_file",
        ]:
            x_root.attrib.pop(att)
    tree.write(
        new_file_path,
        pretty_print=True,
        xml_declaration=False,
        encoding="UTF-8",
    )
    with open(new_file_path, "r+") as f:
        content = f.read()
        content = content.replace(
            '<!DOCTYPE Eintrag SYSTEM "../doctype/oeblexikon.dtd">', ""
        )
        f.seek(0, 0)
        f.write(xml_prefix + content)
    return True


def enrich_verlag_xml(
    xml_file: ET,
    hmi_file: dict,
    target_folder: str = None,
    gideon_index: dict = None,
):
    """Enrich the XML file with information from the HMI file."""
    global count_print_only
    global count_online_only
    global count_print_and_online

    x_root = xml_file.getroot()

    x_root = remove_tag_from_xml(x_root, "Fett")
    x_root = remove_tag_from_xml(x_root, "Hoch")
    if "doi" in hmi_file:
        x_root.set("doi", hmi_file["doi"])
    if "eoebl_id" in hmi_file:
        x_root.set("eoebl_id", hmi_file["eoebl_id"])
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
        x_root.get("eoebl_id"),
        gideon_index,
        "online" if "online" in x_root.find(".//Lieferung").text.lower() else "print",
    )
    elem_lexikonartikel = x_root.find(".//Lexikonartikel")
    elem_lexikonartikel.attrib.pop("type", None)
    elem_lexikonartikel.text = None
    if "Baumfeld_Rudolf-Lothar" in x_root.get("Nummer"):
        pass
    file_name_search_print = (
        x_root.get("Nummer") + ".xml"
        if not x_root.get("Nummer").endswith(".xml")
        else x_root.get("Nummer")
    )
    if len(x_root.findall(".//Lieferung")) == 2 or file_name_search_print in [
        "Amon_Anton_1862_1931.xml",
        "Blaas_Karl_1815_1894.xml",
        "Bremser_Johann-Gottfried_1767_1827.xml",
        "Budik_Peter-Alcantara_1790_1858.xml",
        "Conrad-Hoetzendorf_Franz_1852_1925.xml",
        "Defregger_Franz_1835_1921.xml",
        "Diesing_Karl-Moritz_1800_1867.xml",
        "Terramare_Georg_1889_1948.xml",
        "Falkenhayn_Julius_1829_1899.xml",
        "Goldmark_Carl_1830_1915.xml",
        "Huelgerth_Ludwig_1875_1939.xml",
        "Kandler_Pietro_1804_1872.xml",
        "Kiesewetter_Irene_1809_1872.xml",
        "Kner_Rudolf_1810_1869.xml",
        "Kolessa_Oleksandr-Mychajlovyc_1867_1945.xml",
        "Loehr_Alexander_1885_1947.xml",
        "Pirchan_Emil_1844_1928.xml",
    ]:
        ret = copy_print_version(
            x_root.get("Nummer") + ".xml"
            if not x_root.get("Nummer").endswith(".xml")
            else "",
            hmi_file.get("eoebl_id", None),
            gideon_index,
            hmi_file,
            target_folder,
        )
        if ret:
            x_root.set("Version", "2")
            count_print_and_online += 1
        else:
            x_root.set("Version", "1")
            if "online" in x_root.find(".//Lieferung").text.lower():
                count_online_only += 1
            else:
                count_print_only += 1
    else:
        x_root.set("Version", "1")
        lieferung = x_root.find(".//Lieferung")
        if "online" in lieferung.text.lower():
            count_online_only += 1
        else:
            count_print_only += 1
    if additional_data["PubInfo"] is not None:
        x_root.find(".//Lexikonartikel").append(additional_data["PubInfo"])
        x_root.find(".//Lexikonartikel").remove(x_root.find(".//Lieferung"))
    else:
        lieferung = x_root.findall(".//Lieferung")
        if len(lieferung) == 1:
            lieferung[0].tag = "PubInfo"
        elif len(lieferung) == 2:
            lieferung.sort(
                key=lambda elem: (
                    re.search(r"[0-9]{4}", elem.text).group(0) if elem.text else "0"
                ),
                reverse=True,
            )
            lieferung[0].tag = "PubInfo"
            for elem in lieferung[1:]:
                x_root.find(".//Lexikonartikel").remove(elem)

    vita = x_root.find(".//Lexikonartikel/Vita")
    if additional_data["Geburt"] is not None:
        vita.remove(x_root.find(".//Geburt"))
        vita.append(additional_data["Geburt"])
    if additional_data["Tod"] is not None:
        vita.remove(x_root.find(".//Tod"))
        vita.append(additional_data["Tod"])
    if not x_root.get("Nummer").endswith(".xml"):
        x_root.set("Nummer", x_root.get("Nummer") + ".xml")
    x_root.find(".//Lexikonartikel").text = None
    x_root.find(".//Lexikonartikel").tail = None
    if x_root.find(".//Kurzdefinition") is not None:
        x_root.find(".//Kurzdefinition").tail = None
    if x_root.find(".//Haupttext") is not None:
        x_root.find(".//Haupttext").tail = None
    return xml_file


def get_normalized_file_name(file_name: str) -> str:
    with open("/workspaces/oebl-apis-rdf/OEBL_Print_UND_Online_Liste.csv", "r") as file:
        file_list = csv.reader(file, delimiter=",", quotechar='"')
        for row in file_list:
            if file_name in row:
                return row[1].replace("_online", "")
    return file_name.replace("_online", "")


def create_gideon_index(gideon_dirs: list, verlag_dir: str = None):
    verlag_list = []
    if verlag_dir:
        for subdir, dirs, files in os.walk(verlag_dir):
            for file in files:
                if file.endswith(".xml"):
                    file_path = os.path.join(subdir, file + ".hmi")
                    data_hmi = parse_hmi_file(file_path)
                    if "eoebl_id" not in data_hmi:
                        # logger.warning(f"No eoebl_id found in {file_path}")
                        continue
                    verlag_list.append((file, data_hmi["eoebl_id"]))
    gideon_list = dict()
    for directory in gideon_dirs:
        for subdir, dirs, files in os.walk(directory):
            for file in files:
                if (
                    file.endswith(".xml")
                    and not file.endswith("_Reg.xml")
                    and not file.endswith("_Verweis.xml")
                ):

                    file_path = os.path.join(subdir, file)
                    parser = ET.XMLParser(remove_comments=True, remove_pis=True)
                    tree = ET.parse(file_path, parser)
                    remove_namespace(tree, "{http://www.biographien.ac.at}")
                    root = tree.getroot()
                    oeblid = root.get("eoebl_id", None)
                    if oeblid is None:
                        # logger.warning(f"No oebl_id found in {file_path}")
                        reg_file = file_path.replace(".xml", "_Reg.xml")
                        if os.path.exists(reg_file):
                            tree2 = ET.parse(reg_file, parser)
                            remove_namespace(tree2, "{http://www.biographien.ac.at}")
                            root2 = tree2.getroot()
                            oeblid = root2.get("eoebl_id", None)
                            # if oeblid is None:
                            #     logger.warning(f"No oebl_id found in {reg_file}")
                        if (
                            os.path.exists(file_path.replace(".xml", "_online.xml"))
                            and oeblid is None
                        ):
                            online_file = file_path.replace(".xml", "_online.xml")
                            tree2 = ET.parse(online_file, parser)
                            remove_namespace(tree2, "{http://www.biographien.ac.at}")
                            root2 = tree2.getroot()
                            oeblid = root2.get("eoebl_id", None)
                            # if oeblid is None:
                            #     logger.warning(f"No oebl_id found in {online_file}")

                        # else:
                        #     logger.warning(f"No oebl_id found in {file_path}")
                    pubinfo = root.find(".//PubInfo")
                    if pubinfo is None:
                        pubinfo = root.find(".//Lieferung")
                        if pubinfo is None:
                            logger.warning(f"No PubInfo found in {file_path}")
                            continue
                    pubinfo = pubinfo.text
                    if oeblid not in gideon_list and oeblid is not None:
                        gideon_list[oeblid] = {
                            "online"
                            if "online" in pubinfo.lower()
                            else "print": file_path
                        }
                    elif oeblid is not None:
                        kind = "online" if "online" in pubinfo.lower() else "print"
                        if kind in gideon_list[oeblid]:
                            logger.warning(f"Multiple {kind} found for {oeblid}")
                            continue
                        else:
                            gideon_list[oeblid][kind] = file_path
                    file_adapted = get_normalized_file_name(file)
                    if file_adapted not in gideon_list:
                        gideon_list[file_adapted] = {
                            "online"
                            if "online" in pubinfo.lower()
                            else "print": file_path
                        }
                    else:
                        kind = "online" if "online" in pubinfo.lower() else "print"
                        if kind in gideon_list[file_adapted]:
                            logger.warning(f"Multiple {kind} found for {file_adapted}")
                        else:
                            gideon_list[file_adapted][kind] = file_path
    return gideon_list


def create_harmonized_xmls(
    verlag_folder: str,
    output_folder: str,
    relaxng_file: str = "/workspaces/oebl-apis-rdf/apis-oebl-export/oebl_relax_ng_v1.rng",
    gideon_folders: list = [
        "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Nachtrag",
        "/workspaces/oebl-apis-rdf/oebl-xml-gideon/oebl_consolidated_xml_korrigiert_09-04-2024",
        "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_UND_Online",
        "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Online_only",
        "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_only",
    ],
    # gideon_online_folder: str = "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Online_only",
    # gideon_online_and_print_folder: str = "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_UND_Online",
    # gideon_print_folder: str = "/workspaces/oebl-apis-rdf/oebl-xml-gideon/Print_only",
):
    """Run through the folder of XMLs and enrich them with information
    from the HMI file. Save the enriched XMLs in the output folder."""

    global count_print_only
    global count_online_only
    global count_print_and_online
    global count_verweise
    gideon_index = create_gideon_index(gideon_folders, verlag_folder)
    with open(relaxng_file, "r") as relaxng_file:
        relaxng_doc = ET.parse(relaxng_file)
        relaxng = ET.RelaxNG(relaxng_doc)
    for subdir, dirs, files in os.walk(verlag_folder):
        for file in files:
            if file.endswith("Verweis.xml"):
                logger.info(f"File is Verweis, skipping: {file}")
                count_verweise += 1
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
                    try:
                        parser = ET.XMLParser(remove_comments=True, remove_pis=True)
                        tree = ET.parse(xml_file, parser)
                    except (ET.ParseError, UnicodeDecodeError) as e:
                        logger.error(f"Error parsing file: {file_path}, {e}")
                        continue
                    # if tree.getroot().get("Nummer") in [
                    #     "Koeroesy-Szanto_Josef_1844_1906.xml",
                    #     "Koszta_Jozsef_1861_1949.xml",
                    # ]:
                    #     logger.info(
                    #         f"Broken file {tree.getroot().get('Nummer')}, skipping"
                    #     )
                    #     continue
                    if len(tree.getroot().findall("./Verweis")) > 0:
                        logger.info(f"{file} is Verweis, skipping")
                        count_verweise += 1
                        continue
                    if tree.getroot().find(".//Lieferung") is None:
                        logger.info(f"{file} has no Lieferung, skipping")
                        continue
                    if tree.getroot().find(".//Lieferung") is not None:
                        if tree.getroot().find(".//Lieferung").text is not None:
                            if (
                                "miterwähnt"
                                in tree.getroot().find(".//Lieferung").text.lower()
                            ):
                                logger.info(f"{file} is miterwähnt, skipping")
                                continue
                    hmi_file = parse_hmi_file(file_path + ".hmi")
                    xml_neu = enrich_verlag_xml(
                        tree, hmi_file, output_folder, gideon_index
                    )
                    # Remove 'Lieferungen'  from XML
                    for lieferung in xml_neu.findall(".//Lieferung"):
                        xml_neu.find(".//Lexikonartikel").remove(lieferung)
                    # Save the enriched XML file
                    output_file = os.path.join(output_folder, file)
                    xml_neu.write(
                        output_file,
                        pretty_print=True,
                        xml_declaration=False,
                        encoding="UTF-8",
                    )
                    xml_valid = relaxng.validate(xml_neu)
                    if not xml_valid:
                        logger.error(f"XML is not valid: {file}")
                        logger.error(relaxng.error_log)
                    with open(output_file, "r+") as f:
                        content = f.read()
                        content = content.replace(
                            '<!DOCTYPE Eintrag SYSTEM "../doctype/oeblexikon.dtd">', ""
                        )
                        f.seek(0, 0)
                        f.write(xml_prefix + content)

    logger.info("Finished processing all files.")
    logger.info(f"Print only: {count_print_only}")
    logger.info(f"Online only: {count_online_only}")
    logger.info(f"Print and online: {count_print_and_online}")
    logger.info(f"Verweise (skipped and not copied): {count_verweise}")


def main():
    parser = argparse.ArgumentParser(description="Create harmonized XMLs.")
    parser.add_argument(
        "--input_dir_verlag",
        help="Input directory containing the original XML files from Verlag.",
    )
    parser.add_argument(
        "--output_dir", help="Output directory to save the harmonized XML files."
    )
    # parser.add_argument(
    #     "input_dir_gideon_online",
    #     help="Input directory containing the original XML files from Gideon (online only).",
    # )
    # parser.add_argument(
    #     "input_dir_gideon_online_and_print",
    #     help="Input directory containing the original XML files from Gideon (online and print).",
    # )
    # parser.add_argument(
    #     "input_dir_gideon_print",
    #     help="Input directory containing the original XML files from Gideon (print only).",
    # )
    # parser.add_argument("relaxng", help="Relaxng schema file.")
    args = parser.parse_args()
    create_harmonized_xmls(args.input_dir_verlag, args.output_dir)


if __name__ == "__main__":
    main()
