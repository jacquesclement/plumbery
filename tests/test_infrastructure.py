#!/usr/bin/env python

"""
Tests for `infrastructure` module.
"""

import unittest

from libcloud.compute.drivers.dimensiondata import DimensionDataNodeDriver
from mock_api import DimensionDataMockHttp

from plumbery.engine import PlumberyEngine
from plumbery.facility import PlumberyFacility
from plumbery.infrastructure import PlumberyInfrastructure

DIMENSIONDATA_PARAMS = ('user', 'password')


class FakeDomain:

    id = 123


class FakeNetwork:

    id = 123


class FakePlumbery:

    safeMode = False

    def get_balancer_driver(self, region):
        return None


class FakeLocation:

    id = 'EU6'


fakeParameters = {
    'regionId': 'dd-na',
    'locationId': 'NA9'
}

fakeBlueprints = [{
        'fake': {
            'domain': {
                'name': 'VDC1',
                'service': 'ADVANCED',
                'description': 'fake'},
            'ethernet': {
                'name': 'vlan1',
                'subnet': '10.0.10.0',
                'description': 'fake'},
            'nodes': [{
                'stackstorm': {
                    'description': 'fake',
                    'appliance': 'RedHat 6 64-bit 4 CPU'
                    }
                }]
            }
        }]


class FakeFacility:

    plumbery = FakePlumbery()

    parameters = fakeParameters
    blueprints = fakeBlueprints

    DimensionDataNodeDriver.connectionCls.conn_classes = (
        None, DimensionDataMockHttp)
    DimensionDataMockHttp.type = None
    region = DimensionDataNodeDriver(*DIMENSIONDATA_PARAMS)

    location = FakeLocation()

    _cache_network_domains = []
    _cache_vlans = []

    def get_location_id(self):
        return 'EU6'

    def get_parameter(self, label):
        if label in self.parameters:
            return self.parameters[label]

        return None

fakeBluePrint = {'target': 'fake',
                 'domain': {'name': 'fake',
                            'service': 'ADVANCED',
                            'description': '#vdc1'},
                 'ethernet': {'name': 'fake',
                              'subnet': '10.0.10.0',
                              'description': '#vdc1'}}

defaultsPlan = """
---
safeMode: True
defaults:
  locationId: EU6
  regionId: dd-eu
  ipv4: auto
cloud-config:
  disable_root: false
  ssh_pwauth: true
  ssh_keys:
    rsa_private: |
      {{ pair1.rsa_private }}

    rsa_public: "{{ pair1.ssh.rsa_public }}"

---
blueprints:

  - myBlueprint:
      domain:
        name: myDC
      ethernet:
        name: myVLAN
        subnet: 10.1.10.0
      nodes:
        - myServer
"""


class TestPlumberyInfrastructure(unittest.TestCase):

    def setUp(self):
        facility = FakeFacility()
        self.infrastructure = PlumberyInfrastructure(facility=facility)

    def tearDown(self):
        self.infrastructure = None

    def test_build(self):
        self.infrastructure.build(fakeBluePrint)

    def test_name_listener(self):
        self.infrastructure.blueprint = fakeBluePrint
        name = self.infrastructure.name_listener('fake')
        self.assertEqual(name, 'fake_eu6.fake.listener')

    def test_get_listener(self):
        self.infrastructure.blueprint = fakeBluePrint
        listener = self.infrastructure._get_listener('fakeListener')
        self.assertEqual(listener, None)

    def test_name_pool(self):
        self.infrastructure.blueprint = fakeBluePrint
        name = self.infrastructure._name_pool()
        self.assertEqual(name, 'fake_eu6.pool')

    def test_get_pool(self):
        self.infrastructure.blueprint = fakeBluePrint
        pool = self.infrastructure._get_pool()
        self.assertEqual(pool, None)

    def test_get_container(self):
        container = self.infrastructure.get_container(fakeBluePrint)
        self.assertEqual(container.domain, None)
        self.assertEqual(container.network, None)

    def test_get_ethernet(self):
        self.infrastructure.get_ethernet('MyNetwork')
#        self.infrastructure.get_ethernet(['XY6', 'MyNetwork'])
#        self.infrastructure.get_ethernet(['dd-eu', 'EU6', 'MyNetwork'])

    def test_get_ipv4(self):
        self.infrastructure.blueprint = fakeBluePrint
        self.infrastructure._get_ipv4()

    def test_get_default(self):
        engine = PlumberyEngine()
        engine.from_text(defaultsPlan)
        facility = engine.list_facility('EU6')[0]
        infrastructure = PlumberyInfrastructure(facility)
        self.assertEqual(infrastructure.get_default('ipv4'), 'auto')

if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
