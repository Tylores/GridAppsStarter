from gridappsd import GridAPPSD, topics as t
from gridappsd.simulation import Simulation
import json
from tabulate import tabulate
import pandas as pd
import time

import os
os.environ['GRIDAPPSD_USER'] = 'tutorial_user'
os.environ['GRIDAPPSD_PASSWORD'] = '12345!'
os.environ['GRIDAPPSD_ADDRESS'] = 'localhost'
os.environ['GRIDAPPSD_PORT'] = '61613'

global exit_flag, df_sw_meas, simulation_id, count, load_meas
count = 5

def on_message(headers, message):
    pub_topic = t.simulation_input_topic(simulation_id)

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

        print(message)
        exit()

def query_switches(feeder_mrid, model_api_topic, gapps):
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

def main():
    gapps = GridAPPSD()
    assert gapps.connected

    model_info = gapps.query_model_info()
    feeder_mrid = model_info['data']['models'][0]['modelId']

    # This topic is different for different API
    model_api_topic = "goss.gridappsd.process.request.data.powergridmodel"
    t.REQUEST_POWERGRID_DATA

    run123_config = json.load(open("run-123.json"))
    simulation_obj = Simulation(gapps, run123_config) # Create Simulation object

    simulation_obj.start_simulation() # Start Simulation
    simulation_id = simulation_obj.simulation_id # Obtain Simulation ID
    
    query_switches(feeder_mrid, model_api_topic, gapps)

    message = {
        "modelId": feeder_mrid,
        "requestType": "QUERY_OBJECT_DICT",
        "resultFormat": "JSON",
        "objectType": "LoadBreakSwitch"
    }
    sw_dict = gapps.get_response(model_api_topic, message, timeout=10)
    print(sw_dict)
    
    message = {
        "modelId": feeder_mrid,
        "requestType": "QUERY_OBJECT_MEASUREMENTS",
        "resultFormat": "JSON",
        "objectType": "LoadBreakSwitch"
    }
    sw_meas = gapps.get_response(model_api_topic, message, timeout=10)
    sw_meas = sw_meas['data']
    
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

    sim_output_topic = t.simulation_output_topic(simulation_id)

    # following function allows us to subscribe the simulation output
    # Need a call back function
    gapps.subscribe(sim_output_topic, on_message)

    exit_flag = False

    while not exit_flag:
        time.sleep(0.1)

if __name__ == "__main__":
    main()