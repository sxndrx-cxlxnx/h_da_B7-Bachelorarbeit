import json
import re
import requests
import os

# ******************************************************************************************************
unwanted_tests = {
    "natc_dev_nonHA": {
        "BUILD": ["warn"],
        "PROMO": [],
        "qabat": [],
        "QAONL": ["objhha", "parmha", "rpcha"],
        "QAPRD852": [],
        "QAPRD861": []
    },
    "natc_dev_HA": {
        "BUILD": ["warn"],
        "PROMO": [],
        "qabat": [],
        "QAONL": []
    },
    "natc_931": {
        "BUILD": ["warn"],
        "PROMO": [],
        "qabat": []
    },
    "natc_932": {
        "BUILD": ["warn"],
        "PROMO": [],
        "qabat": []
    }
}
ignored_tests = {
    "natc_dev_nonHA": {
        "qabat": ["dact"]
    },
    "natc_dev_HA": {
        "qabat": ["dact"]
    },
    "natc_931": {
        "qabat": []
    },
    "natc_932": {
        "qabat": []
    }
}

def get_list_from_scresult(natvers, node, key, date):                   # TODO: new name for function - curl is not what is done
    url = "https://natosweb.eur.ad.sag:4433/nww3/mod/scres/scres?"
    
    # curl the pythonic way
    payload = {"natvers" : natvers, "node" : node, "key" : key, "DATE" : date}
    request = requests.get(url,
                           params = payload,
                           verify = False)
    output = request.text

    # ******************************************************************************************************
    # initializing substrings
    sub1 = "<pre class='result'>"
    sub2 = "</pre>"
    curl_result = ""

    while(output.find(sub1) >= 0):
        # getting index of substrings
        idx1 = output.find(sub1) - 1
        idx2 = output.find(sub2)
        
        # length of substring 1 is added to
        # get string from next character
        res = output[idx1 + len(sub1) + 1: idx2]
        curl_result = curl_result + res

        # reset string
        output = output[idx2 + len(sub2):]

    #return curl_result
    all_lines = curl_result.split('\n')
    return all_lines

def get_dict_of_lines(all_lines):
    category_of_line = ""
    dict_of_lines = {}

    for line in all_lines[1:]:
        if line == "":
            continue

        if re.match('[a-z]*:', line) :
            category_of_line = "BUILD"
        else :
            category_of_line = line.split(' ', 1)[0]

        if category_of_line in dict_of_lines:
            dict_of_lines[category_of_line].append(line)
        else:
            dict_of_lines[category_of_line] = [line]
    return dict_of_lines

def get_tests_of_a_key_list(dict_of_lines, key):
    tests_of_a_key_list = []

    for line in dict_of_lines[key]:
        # TODO - currrently removed, maybe needed
        if "First".lower() in line.lower() or "init".lower() in line.lower():
            dict_of_lines[key].remove(line)
            continue

        tests_of_a_line_list = [x.strip(":") for x in line.split()]
        tests_of_a_key_list = tests_of_a_key_list + tests_of_a_line_list
    tests_of_a_key_list = [value for value in tests_of_a_key_list if value != key]
    
    return tests_of_a_key_list

def convert_list_to_dictlist(lst):
    #res_dict = {}
    res_list = []
    for i in range(0, len(lst), 2):
        if(len( lst[i+1] ) > 1):
            """
            -       heute noch nicht gelaufen
            n/a     gibts in der Umgebung nicht
            Err     Fehler
            Ok      ok
            CORE    crashed
            """
            if(lst[i+1] == "N/A"): continue
            if(lst[i+1] == "OK"): lst[i+1] = "0"
            #if(lst[i+1] == "Err"): lst[i+1] = -1
            #if(lst[i+1] == "CORE"): lst[i+1] = -2

        if lst[i+1].isnumeric():
            #res_dict[lst[i]] = int(lst[i + 1])
            res_list.append({ "testname" : lst[i], "result" : int(lst[i + 1]) })
        else:
            #res_dict[lst[i]] = lst[i + 1]
            res_list.append({ "testname" : lst[i], "result" : lst[i + 1] })

    #return res_dict
    return res_list

def remove_elements_from_dictlist(name_of_env, category, dict_list, unwanted_elements):# TODO

    if name_of_env in unwanted_elements:
        environment = unwanted_elements[name_of_env]
        if category in environment:
            indices_to_delete = []
            for element in dict_list:
                if element["testname"] in environment[category]:
                    el_index = dict_list.index(element)
                    indices_to_delete = [el_index] + indices_to_delete

            for index in indices_to_delete:
                del dict_list[index]

            return dict_list
        
        else:
            return []

# main functionality
def parse_to_json(name_of_env, natvers, node, key, date, path):

    all_lines_without_n = get_list_from_scresult(natvers, node, key, date)

    # strip lines and store relevant ones
    all_lines = [x.strip() for x in all_lines_without_n]

    test_results_dict = {}
    test_results_dict["test_categories"] = {}

    dict_of_lines = get_dict_of_lines(all_lines)

    test_categories_list = []

    for key in dict_of_lines:
        tests_of_a_key_list = get_tests_of_a_key_list(dict_of_lines, key)

        tests_of_a_key_dictlist = convert_list_to_dictlist(tests_of_a_key_list)
        tests_of_a_key_dictlist = remove_elements_from_dictlist(name_of_env, key, tests_of_a_key_dictlist, unwanted_tests)
        
        if tests_of_a_key_dictlist == []:
            continue

        current_category = {"category" : key, "tests" : tests_of_a_key_dictlist}
        test_categories_list.append(current_category)

    test_results_dict['test_categories'] = test_categories_list

    category_stats_list = []
    for category_el in test_results_dict['test_categories']:
        current_category = {}
        this_category = category_el["category"]


        errors = 0
        pending = 0
        crashed = 0
        ignored = 0

        for test_el in category_el["tests"]:
            if this_category in ignored_tests[name_of_env] and test_el["testname"] in ignored_tests[name_of_env][this_category]:
                ignored = ignored + test_el["result"]
            elif test_el["result"] == "-":
                pending += 1
            elif test_el["result"] == "CORE":
                crashed += 1
            elif test_el["result"] == "Err":
                errors += 1
            else:
                errors = errors + test_el["result"]

        current_category = {"category" : this_category,
                            "crashed" : crashed,
                            "errors" : errors,
                            "pending" : pending,
                            "ignored" : ignored}
        
        category_stats_list.append(current_category)

    stats_dict = {}
    stats_dict['test_categories'] = category_stats_list

    # Convert and write JSON object to file
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as outfile: 
        #json.dump(test_results_dict, outfile, indent=2)
        json.dump(stats_dict, outfile, indent=2)

    print("---   Parsing " + name_of_env + " done   ---")

# ******************************************************************************************************
#           MAIN
# ******************************************************************************************************

# develop
parse_to_json(name_of_env   = "natc_dev_nonHA",
              natvers       = "931",
              node          = "daerednatqe8",
              key           = "count",
              date          = "",
              path          = "../files/dev/scresult_natc_dev_nonHA.json")
parse_to_json(name_of_env   = "natc_dev_HA",
              natvers       = "931",
              node          = "daerednatdev8",
              key           = "count",
              date          = "",
              path          = "../files/dev/scresult_natc_dev_HA.json")

# released
parse_to_json(name_of_env   = "natc_931",
              natvers       = "931D",
              node          = "daerednatqe8",
              key           = "count",
              date          = "",
              path          = "../files/rel/scresult_natc_931.json")
parse_to_json(name_of_env   = "natc_932",
              natvers       = "931G",
              node          = "daerednatqe8",
              key           = "count",
              date          = "",
              path          = "../files/rel/scresult_natc_932.json")

print("---   Program done   ---")