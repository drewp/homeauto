import logging
from typing import cast
import unittest

from rdflib.graph import ConjunctiveGraph

from inference import Inference
from inference_test import N3
from rdflib_debug_patches import patchBnodeCounter, patchSlimReprs

patchSlimReprs()
patchBnodeCounter(always=False)

logging.basicConfig(level=logging.DEBUG)

# ~/.venvs/mqtt_to_rdf/bin/nosetests --with-watcher --logging-level=INFO --with-timer -s --nologcapture infer_perf_test


class TestPerf(unittest.TestCase):

    def test(self):
        config = ConjunctiveGraph()
        config.parse('conf/rules.n3', format='n3')

        inference = Inference()
        inference.setRules(config)
        expandedConfig = inference.infer(config)
        expandedConfig += inference.nonRuleStatements()
        print(cast(bytes, expandedConfig.serialize(format='n3')).decode('utf8'))
        self.fail()

        for loop in range(50):
            # g = N3('''
            # <urn:uuid:2f5bbe1e-177f-11ec-9f97-8a12f6515350> a :MqttMessage ;
            #     :body "online" ;
            #     :onlineTerm :Online ;
            #     :topic ( "frontdoorlock" "status") .
            # ''')
            # derived = inference.infer(g)

            # g = N3('''
            # <urn:uuid:2f5bbe1e-177f-11ec-9f97-8a12f6515350> a :MqttMessage ;
            #     :body "zz" ;
            #     :bodyFloat 12.2;
            #     :onlineTerm :Online ;
            #     :topic ( "air_quality_outdoor" "sensor" "bme280_temperature" "state") .
            # ''')
            # derived = inference.infer(g)
            g = N3('''
            <urn:uuid:a4778502-1784-11ec-a323-464f081581c1> a :MqttMessage ;
                :body "65021" ;
                :bodyFloat 6.5021e+04 ;
                :topic ( "air_quality_indoor" "sensor" "ccs811_total_volatile_organic_compound" "state" ) .
            ''')
            derived = inference.infer(g)

        # self.fail()
