#!/usr/bin/env python3
import json
import requests
import os
import re
import pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

SRC = "https://apis.acdh.oeaw.ac.at/apis/api"

TOKEN = os.environ.get("TOKEN")
HEADERS = {"Authorization": f"Token {TOKEN}"}

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape()
)
template = env.get_template("template.xml")

OUTPUT = pathlib.Path("output")


def export_result(result: dict):
    name = result.get("name")
    first_name = result.get("first_name")
    filename = f"{name}_{first_name}".replace(" ", "_")
    outputfile = OUTPUT / pathlib.Path(filename).with_suffix(".xml")
    outputfile.parent.mkdir(parents=True, exist_ok=True)
    outputfile.write_text(template.render(result))


def get_relations(id: int, relation):
    return relation["subj"] == id or relation["obj"] == id


def export_persons():
    professions = json.loads(pathlib.Path("professions.json").read_text())
    professioncats = json.loads(pathlib.Path("professioncats.json").read_text())
    uris = json.loads(pathlib.Path("uris.json").read_text())
    sources = json.loads(pathlib.Path("sources.json").read_text())
    relations = json.loads(pathlib.Path("relations.json").read_text())

    nextpage = f"{SRC}/entities/person/?format=json&limit=1000"
    while nextpage:
        print(nextpage)
        page = requests.get(nextpage, headers=HEADERS)
        data = page.json()
        nextpage = data['next']
        for result in data["results"]:

            source = result.get("source", {})
            if source:
                sourceid = source.get("id")
                result["source"] = sources.get(str(sourceid))

            result["berufe"] = []
            for profession in result.get("profession", []):
                if profession.get("parent_id"):
                    result["berufe"].extend(professions.get(str(profession["id"])))
                else:
                    result["berufsgruppe"] = professioncats.get(str(profession["id"]))
            del result["profession"]

            getrel = lambda x: get_relations(result["id"], x)
            relrelations = filter(getrel, relations.values())
            result["relations"] = list(relrelations)

            result["uris"] = uris.get(str(result["id"]), [])
            print(result["url"])
            export_result(result)


def export_professions():
    nextpage = f"{SRC}/vocabularies/professiontype/?format=json&limit=5500"
    professions = dict()
    professioncats = dict()

    while nextpage:
        print(nextpage)
        page = requests.get(nextpage, headers=HEADERS)
        data = page.json()
        nextpage = data['next']
        for result in data["results"]:
            tokens = re.split(r" und |,", result["name"])
            for pos, token in enumerate(tokens):
                if token.startswith("-"):
                    token = tokens[pos-1] + token
            tokens = [token.strip() for token in tokens]
            professions[result["id"]] = tokens
            if result["parent_class"]:
                professioncats[result["parent_class"]["id"]] = result["parent_class"]["label"]

    pathlib.Path("professions.json").write_text(json.dumps(professions, indent=2))
    pathlib.Path("professioncats.json").write_text(json.dumps(professioncats, indent=2))


def export_uris():
    nextpage = f"{SRC}/metainfo/uri/?format=json&limit=5000"
    uris = dict()

    while nextpage:
        print(nextpage)
        page = requests.get(nextpage, headers=HEADERS)
        data = page.json()
        nextpage = data['next']
        for result in data["results"]:
            if result["id"] in [60485, 64341, 64344, 65675, 67843, 67866, 67870, 67874, 67876, 67878, 74055, 74057, 82548, 82550, 86445, 86447, 86703, 86705, 89010, 89026, 89050, 91406, 91477, 92307, 92311, 92317, 92319, 92916, 92933, 92941, 92950, 92969, 92988, 92992, 93001, 93007, 93040, 93044, 93050, 93054, 93059, 93064, 93088, 93109, 93113, 93119, 93142, 93149, 93155, 93213, 93237, 93250, 93260, 93262, 93266, 93295, 93318, 93320, 93324, 93341, 93358, 93376, 93388, 93392, 93409, 93442, 93459, 93478, 93482, 93499, 93517, 93531, 93548, 93555, 93589, 93609, 93616, 93697, 93720, 93727, 93740, 93747, 93756, 93785, 93851, 93863, 93926, 93934, 93948, 93958, 93968, 93980, 94004, 94044, 94072, 94111, 94198, 94202, 94206, 94237, 94268, 94317, 94354, 94375, 94398, 94450, 94456, 94463, 94477, 94490, 94498, 94511, 94622, 94638, 94683, 94779, 94873, 94919, 94958, 95111, 95124, 95146, 95190, 95194, 95274, 95284, 95305, 95309, 95339, 95449, 95534, 95610, 95616, 95620, 95626, 95655, 95668, 95672, 95696]:
                continue
            if result["uri"] == "https://apis-edits.acdh-dev.oeaw.ac.at/entity/None/":
                continue
            if result["uri"] == "":
                continue
            if result.get("entity") is None:
                continue
            if result["entity"]["id"] not in uris:
                uris[result["entity"]["id"]] = []
            uris[result["entity"]["id"]].append(result["uri"])

    pathlib.Path("uris.json").write_text(json.dumps(uris, indent=2))


def export_sources():
    nextpage = f"{SRC}/metainfo/source/?format=json&limit=1000"
    sources = dict()

    while nextpage:
        print(nextpage)
        page = requests.get(nextpage, headers=HEADERS)
        data = page.json()
        nextpage = data['next']
        for result in data["results"]:
            print(result["url"])
            sources[result["id"]] = {
                    "orig_filename": result["orig_filename"],
                    "pubinfo": result["pubinfo"],
                    "author": result["author"]
            }
    pathlib.Path("sources.json").write_text(json.dumps(sources, indent=2))


def export_relations():
    relations = {
            'personevent': {
                "subj": "related_person",
                "obj": "related_event",
            },
            'personinstitution': {
                "subj": "related_person",
                "obj": "related_institution"
            },
            "personperson": {
                "subj": "related_personA",
                "obj": "related_personB",
            },
            "personplace": {
                "subj": "related_person",
                "obj": "related_place",
            },
            "personwork": {
                "subj": "related_person",
                "obj": "related_work",
            },
            "placeplace": {
                "subj": "related_placeA",
                "obj": "related_placeB",
            },
            "institutioninstitution": {
                "subj": "related_institutionA",
                "obj": "related_institutionB",
            }
    }
    propertylist = {}
    relationlist = {}

    s = requests.Session()

    COPYFIELDS = ['review', 'start_date', 'start_start_date', 'start_end_date', 'end_date', 'end_start_date', 'end_end_date', 'start_date_written', 'end_date_written']
    for relation, relationsettings in relations.items():
        nextpage = f"{SRC}/relations/{relation}/?format=json&limit=5000"
        while nextpage:
            print(nextpage)
            page = s.get(nextpage, headers=HEADERS)
            data = page.json()
            nextpage = data["next"]
            for result in data["results"]:
                if result["relation_type"]:
                    propdata = propertylist.get(result["relation_type"]["id"])
                    if not propdata:
                        proppage = s.get(result["relation_type"]["url"])
                        propdata = proppage.json()
                        propertylist[result["relation_type"]["id"]] = propdata
                    if result[relationsettings["subj"]] and result[relationsettings["obj"]]:
                        relationlist[result["id"]] = {
                            "name": propdata["name"],
                            "name_reverse": propdata["name_reverse"] or propdata["name"] + " (reverse)",
                            "subj": result[relationsettings["subj"]]["id"],
                            "obj": result[relationsettings["obj"]]["id"],
                        }
                        for field in COPYFIELDS:
                            relationlist[result["id"]][field] = result[field]
                    else:
                        print(result)
                else:
                    print(f"No relation type for relation {result}")
    pathlib.Path("relations.json").write_text(json.dumps(relationlist, indent=2))


if __name__ == "__main__":
    #export_sources()
    #export_uris()
    #export_professions()
    #export_relations()
    export_persons()
