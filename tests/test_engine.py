#!/usr/bin/env python

"""
Tests for `plumbery` module.
"""

import logging
import os
import socket
import unittest

from Crypto.PublicKey import RSA
import ast

from libcloud.common.types import InvalidCredsError

from plumbery.__main__ import parse_args, main
from plumbery.engine import PlumberyEngine
from plumbery import __version__

myPlan = """
---
safeMode: True
cloud-config:
  disable_root: false
  ssh_pwauth: true
  ssh_keys:
    rsa_private: |
      {{ pair1.rsa_private }}

    rsa_public: "{{ pair1.ssh.rsa_public }}"

---
# Frankfurt in Europe
locationId: EU6
regionId: dd-eu

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

myFacility = {
    'regionId': 'dd-eu',
    'locationId': 'EU7',
    'blueprints': [{
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
    }


class FakeLocation:

    id = 'EU7'
    name = 'data centre in Amsterdam'
    country = 'Netherlands'


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


class TestPlumberyEngine(unittest.TestCase):

    def test_set(self):

        settings = {
            'safeMode': False,
            'polishers': [
                {'ansible': {}},
                {'spit': {}},
                ]
            }

        self.engine = PlumberyEngine()
        self.engine.set_shared_secret('fake_secret')
        self.assertEqual(self.engine.get_shared_secret(), 'fake_secret')

        random = self.engine.get_secret('random')
        self.assertEqual(len(random), 9)
        self.assertEqual(self.engine.get_secret('random'), random)

        self.engine.set_user_name('fake_name')
        self.assertEqual(self.engine.get_user_name(), 'fake_name')

        self.engine.set_user_password('fake_password')
        self.assertEqual(self.engine.get_user_password(), 'fake_password')

        self.engine.set(settings)
        self.assertEqual(self.engine.safeMode, False)

        try:
            self.engine.from_text(myPlan)
            cloudConfig = self.engine.get_cloud_config()
            self.assertEqual(len(cloudConfig.keys()), 3)
            self.engine.add_facility(myFacility)
            self.assertEqual(len(self.engine.facilities), 2)

        except socket.gaierror:
            pass
        except InvalidCredsError:
            pass

    def test_lifecycle(self):

        self.engine = PlumberyEngine()
        self.engine.set_shared_secret('fake_secret')
        self.assertEqual(self.engine.get_shared_secret(), 'fake_secret')

        self.engine.set_user_name('fake_name')
        self.assertEqual(self.engine.get_user_name(), 'fake_name')

        self.engine.set_user_password('fake_password')
        self.assertEqual(self.engine.get_user_password(), 'fake_password')

        try:
            self.engine.do('build')
            self.engine.build_all_blueprints()
            self.engine.build_blueprint('myBlueprint')

            self.engine.do('start')
            self.engine.start_all_blueprints()
            self.engine.start_blueprint('myBlueprint')

            self.engine.do('polish')
            self.engine.polish_all_blueprints()
            self.engine.polish_blueprint('myBlueprint')

            self.engine.do('stop')
            self.engine.stop_all_blueprints()
            self.engine.stop_blueprint('myBlueprint')

            self.engine.wipe_all_blueprints()
            self.engine.wipe_blueprint('myBlueprint')

            self.engine.do('destroy')
            self.engine.destroy_all_blueprints()
            self.engine.destroy_blueprint('myBlueprint')

        except socket.gaierror:
            pass
        except InvalidCredsError:
            pass

    def test_lookup(self):

        self.engine = PlumberyEngine()
        self.assertEqual(self.engine.lookup('plumbery.version'), __version__)

        self.engine.secrets = {}
        random = self.engine.lookup('random.secret')
        self.assertEqual(len(random), 9)
        self.assertEqual(self.engine.lookup('random.secret'), random)

        md5 = self.engine.lookup('random.md5.secret')
        self.assertEqual(len(md5), 32)
        self.assertNotEqual(md5, random)

        sha = self.engine.lookup('random.sha1.secret')
        self.assertEqual(len(sha), 40)
        self.assertNotEqual(sha, random)

        sha = self.engine.lookup('random.sha256.secret')
        self.assertEqual(len(sha), 64)
        self.assertNotEqual(sha, random)

        id1 = self.engine.lookup('id1.uuid')
        self.assertEqual(len(id1), 36)
        self.assertEqual(self.engine.lookup('id1.uuid'), id1)
        id2 = self.engine.lookup('id2.uuid')
        self.assertEqual(len(id2), 36)
        self.assertNotEqual(id1, id2)

        self.engine.lookup('application.secret')
        self.engine.lookup('database.secret')
        self.engine.lookup('master.secret')
        self.engine.lookup('slave.secret')

        original = 'hello world'
        text = self.engine.lookup('pair1.rsa_public')
        self.assertEqual(text.startswith('ssh-rsa '), True)
        key = RSA.importKey(text)
        encrypted = key.publickey().encrypt(original, 32)

        privateKey = self.engine.lookup('pair1.rsa_private')
        self.assertEqual(privateKey.startswith(
            '-----BEGIN RSA PRIVATE KEY-----'), True)
        key = RSA.importKey(self.engine.lookup('pair1.rsa_private'))
        decrypted = key.decrypt(ast.literal_eval(str(encrypted)))
        self.assertEqual(decrypted, original)

        self.assertEqual(len(self.engine.secrets), 12)

        with self.assertRaises(LookupError):
            localKey = self.engine.lookup('local.rsa_private')

        localKey = self.engine.lookup('local.rsa_public')
        try:
            path = '~/.ssh/id_rsa.pub'
            with open(os.path.expanduser(path)) as stream:
                text = stream.read()
                stream.close()
                self.assertEqual(localKey.strip(), text.strip())
                logging.info("Successful lookup of local public key")

        except IOError:
            pass

    def test_secrets(self):

        engine = PlumberyEngine()
        engine.secrets = {'hello': 'world'}
        engine.save_secrets(plan='test_engine.yaml')
        self.assertEqual(os.path.isfile('.test_engine.secrets'), True)
        engine.secrets = {}
        engine.load_secrets(plan='test_engine.yaml')
        self.assertEqual(engine.secrets['hello'], 'world')
        engine.forget_secrets(plan='test_engine.yaml')
        self.assertEqual(os.path.isfile('.test_engine.secrets'), False)

    def test_defaults(self):

        engine = PlumberyEngine()
        engine.from_text(defaultsPlan)
        self.assertEqual(engine.get_default('locationId'), 'EU6')
        self.assertEqual(engine.get_default('regionId'), 'dd-eu')
        self.assertEqual(engine.get_default('ipv4'), 'auto')

    def test_parser(self):
        args = parse_args(['fittings.yaml', 'build', 'web'])
        self.assertEqual(args.fittings, 'fittings.yaml')
        self.assertEqual(args.action, 'build')
        self.assertEqual(args.blueprints, ['web'])
        self.assertEqual(args.facilities, None)
        args = parse_args(['fittings.yaml', 'build', 'web', '-d'])
        self.assertEqual(
            logging.getLogger().getEffectiveLevel(), logging.DEBUG)
        args = parse_args(['fittings.yaml', 'build', 'web', '-q'])
        self.assertEqual(
            logging.getLogger().getEffectiveLevel(), logging.WARNING)
        args = parse_args(['fittings.yaml', 'start', '@NA12'])
        self.assertEqual(args.fittings, 'fittings.yaml')
        self.assertEqual(args.action, 'start')
        self.assertEqual(args.blueprints, None)
        self.assertEqual(args.facilities, ['NA12'])
        args = parse_args([
            'fittings.yaml', 'rub', 'web', 'sql', '@NA9', '@NA12'])
        self.assertEqual(args.fittings, 'fittings.yaml')
        self.assertEqual(args.action, 'rub')
        self.assertEqual(args.blueprints, ['web', 'sql'])
        self.assertEqual(args.facilities, ['NA9', 'NA12'])
        args = parse_args([
            'fittings.yaml', 'rub', 'web', '@NA9', 'sql', '@NA12'])
        self.assertEqual(args.fittings, 'fittings.yaml')
        self.assertEqual(args.action, 'rub')
        self.assertEqual(args.blueprints, ['web', 'sql'])
        self.assertEqual(args.facilities, ['NA9', 'NA12'])
        args = parse_args(['fittings.yaml', 'polish'])
        self.assertEqual(args.fittings, 'fittings.yaml')
        self.assertEqual(args.action, 'polish')
        self.assertEqual(args.blueprints, None)
        self.assertEqual(args.facilities, None)

    def test_main(self):
        engine = PlumberyEngine()
        engine.from_text(myPlan)
        engine.set_user_name('fake_name')
        engine.set_user_password('fake_password')
        with self.assertRaises(SystemExit):
            main(['bad args'], engine)
        with self.assertRaises(SystemExit):
            main(['fittings.yaml'], engine)
        with self.assertRaises(SystemExit):
            main(['fittings.yaml', 'xyz123', 'web'], engine)
        with self.assertRaises(SystemExit):
            main(['-v'], engine)
        with self.assertRaises(SystemExit):
            main(['fittings.yaml', 'build', 'web', '-v'], engine)

if __name__ == '__main__':
    import sys
    sys.exit(unittest.main())
