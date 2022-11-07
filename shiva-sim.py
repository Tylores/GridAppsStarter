# -------------------------------------------------------------------------------
# Copyright (c) 2017, Battelle Memorial Institute All rights reserved.
# Battelle Memorial Institute (hereinafter Battelle) hereby grants permission to any person or entity
# lawfully obtaining a copy of this software and associated documentation files (hereinafter the
# Software) to redistribute and use the Software in source and binary forms, with or without modification.
# Such person or entity may use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and may permit others to do so, subject to the following conditions:
# Redistributions of source code must retain the above copyright notice, this list of conditions and the
# following disclaimers.
# Redistributions in binary form must reproduce the above copyright notice, this list of conditions and
# the following disclaimer in the documentation and/or other materials provided with the distribution.
# Other than as used herein, neither the name Battelle Memorial Institute or Battelle may be used in any
# form whatsoever without the express written consent of Battelle.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
# BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
# GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
# General disclaimer for use with OSS licenses
#
# This material was prepared as an account of work sponsored by an agency of the United States Government.
# Neither the United States Government nor the United States Department of Energy, nor Battelle, nor any
# of their employees, nor any jurisdiction or organization that has cooperated in the development of these
# materials, makes any warranty, express or implied, or assumes any legal liability or responsibility for
# the accuracy, completeness, or usefulness or any information, apparatus, product, software, or process
# disclosed, or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer,
# or otherwise does not necessarily constitute or imply its endorsement, recommendation, or favoring by the United
# States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the
# UNITED STATES DEPARTMENT OF ENERGY under Contract DE-AC05-76RL01830
# -------------------------------------------------------------------------------
"""
Created on April 13, 2021
@author: Shiva Poudel
"""""

# from shared.sparql import SPARQLManager
# from shared.glm import GLMManager

import networkx as nx
import pandas as pd
import math
import argparse
import json
import sys
import os
import importlib
import numpy as np
import time
from tabulate import tabulate
import re
from datetime import datetime
# import utils

from gridappsd import GridAPPSD, topics, DifferenceBuilder
from gridappsd.topics import simulation_output_topic, simulation_log_topic, simulation_input_topic

global exit_flag, df_sw_meas, simulation_id, count, load_meas
count = 5


def on_message(headers, message):
    global exit_flag, df_sw_meas, simulation_id, count, load_meas
    gapps = GridAPPSD()
    publish_to_topic = simulation_input_topic(simulation_id)
    if type(message) == str:
        message = json.loads(message)

    if 'message' not in message:
        if message['processStatus'] == 'COMPLETE' or \
                message['processStatus'] == 'CLOSED':
            print('End of Simulation')
            exit_flag = True

    else:
        meas_data = message["message"]["measurements"]
        timestamp = message["message"]["timestamp"]
        count += 1
        if count >= 1:
            # Print the switch status just once
            for k in range(df_sw_meas.shape[0]):
                measid = df_sw_meas['measid'][k]
                status = meas_data[measid]['value']
                print(df_sw_meas['name'][k], status)
                print('..................')
        skw = 0
        skvar = 0
        for ld in load_meas:
            measid = ld['measid']
            pq = meas_data[measid]
            phi = (pq['angle']) * math.pi / 180
            kW = 0.001 * pq['magnitude'] * np.cos(phi)
            kVAR = 0.001 * pq['magnitude'] * np.sin(phi)
            print(kW, kVAR)
            # skw += kW
            # skvar += kVAR
        print(message)
        # with open("sample.json", "w") as outfile:
        #     outfile.write(message)
        exit()

        # Prints out the timestamp and load values at each time step.

def query_switches(feeder_mrid, model_api_topic, ):
    gapps = GridAPPSD()
    query = """
        PREFIX r:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX c:  <http://iec.ch/TC57/CIM100#>
        SELECT ?cimtype ?name ?bus1 ?bus2 ?id 
        (group_concat(distinct ?phs;separator="") as ?phases) WHERE {
        SELECT ?cimtype ?name ?bus1 ?bus2 ?phs ?id WHERE {
        VALUES ?fdrid {"%s"}  # 123 bus
        VALUES ?cimraw {c:LoadBreakSwitch}
        ?fdr c:IdentifiedObject.mRID ?fdrid.
        ?s r:type ?cimraw.
        bind(strafter(str(?cimraw),"#") as ?cimtype)
        ?s c:Equipment.EquipmentContainer ?fdr.
        ?s c:IdentifiedObject.name ?name.
        ?s c:IdentifiedObject.mRID ?id.
        ?t1 c:Terminal.ConductingEquipment ?s.
        ?t1 c:ACDCTerminal.sequenceNumber "1".
        ?t1 c:Terminal.ConnectivityNode ?cn1. 
        ?cn1 c:IdentifiedObject.name ?bus1.
        ?t2 c:Terminal.ConductingEquipment ?s.
        ?t2 c:ACDCTerminal.sequenceNumber "2".
        ?t2 c:Terminal.ConnectivityNode ?cn2. 
        ?cn2 c:IdentifiedObject.name ?bus2
        OPTIONAL {?swp c:SwitchPhase.Switch ?s.
        ?swp c:SwitchPhase.phaseSide1 ?phsraw.
        bind(strafter(str(?phsraw),"SinglePhaseKind.") as ?phs) }
        } ORDER BY ?name ?phs
        }
        GROUP BY ?cimtype ?name ?bus1 ?bus2 ?id
        ORDER BY ?cimtype ?name
        """ % feeder_mrid
    results = gapps.query_data(query, timeout=60)
    results_obj = results['data']
    sw_data = results_obj['results']['bindings']
    switches = []
    for p in sw_data:
        sw_mrid = p['id']['value']
        # Store the from and to bus for a switch
        fr_to = [p['bus1']['value'], p['bus2']['value']]
        message = dict(name=p['name']['value'],
                       sw_id=sw_mrid,
                       sw_con=fr_to)
        switches.append(message)
    switches_df = pd.DataFrame(switches)
    print(tabulate(switches_df, headers='keys', tablefmt='psql'))


def _main():
    global simulation_id, df_sw_meas, load_meas
    simulation_id = '1377220941'
    feeder_mrid = '_C1C3E687-6FFD-C753-582B-632A27E28507'

    # This topic is different for different API
    model_api_topic = "goss.gridappsd.process.request.data.powergridmodel"

    # Note: there are other parameters for connecting to
    # systems other than localhost
    gapps = GridAPPSD()
    # gapps = GridAPPSD(username="user", password="pass")
    query_switches(feeder_mrid, model_api_topic)

    message = {
        "modelId": feeder_mrid,
        "requestType": "QUERY_OBJECT_DICT",
        "resultFormat": "JSON",
        "objectType": "LoadBreakSwitch"
    }
    sw_dict = gapps.get_response(model_api_topic, message, timeout=10)
    # print(sw_dict)
    #
    message = {
        "modelId": feeder_mrid,
        "requestType": "QUERY_OBJECT_MEASUREMENTS",
        "resultFormat": "JSON",
        "objectType": "LoadBreakSwitch"
    }
    sw_meas = gapps.get_response(model_api_topic, message, timeout=10)
    sw_meas = sw_meas['data']
    # print(sw_meas)
    # Filter the response based on type
    sw_meas = [e for e in sw_meas if e['type'] == 'Pos']
    print(sw_meas[0])
    df_sw_meas = pd.DataFrame(sw_meas)
    print(df_sw_meas)

    message = {
        "modelId": feeder_mrid,
        "requestType": "QUERY_OBJECT_MEASUREMENTS",
        "resultFormat": "JSON",
        "objectType": "ACLineSegment"
    }
    load_meas = gapps.get_response(model_api_topic, message, timeout=10)
    load_meas = load_meas['data']
    load_meas = [l for l in load_meas if l['type'] == 'VA']
    load_meas_df = pd.DataFrame(load_meas)
    print(load_meas_df)
    load_meas = [l for l in load_meas if l['eqname'] == 'l115']
    # print(load_meas)
    # exit()

    sim_output_topic = simulation_output_topic(simulation_id)

    # following function allows us to subscribe the simulation output
    # Need a call back function
    gapps.subscribe(sim_output_topic, on_message)

    global exit_flag
    exit_flag = False

    while not exit_flag:
        time.sleep(0.1)


if __name__ == "__main__":
    _main()

