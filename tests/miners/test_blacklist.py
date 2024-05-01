import unittest
from unittest.mock import MagicMock, patch
from neurons.miners.blacklist import query_blacklist, base_blacklist, discovery_blacklist
from insights import protocol
from collections import deque
import time

class TestBlackList(unittest.TestCase):

    def setUp(self):
        # Mock objects and setup necessary context
        self.mock_metagraph = MagicMock()
        self.mock_miner_config = MagicMock()
        self.mock_config = MagicMock()

        self.validator = MagicMock()
        self.validator.metagraph = self.mock_metagraph
        self.validator.config = self.mock_config
        self.validator.miner_config = self.mock_miner_config

    def test_base_blacklist_unrecognized_hotkey(self):
        synapse = protocol.BlockCheck()        
        synapse.dendrite.hotkey = 'unrecognized_hotkey'
        self.mock_metagraph.hotkeys = {'some_other_hotkey'}

        result, message = base_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Unrecognized hotkey")

    def test_base_blacklist_protocol_version_mismatch(self):
        synapse = protocol.BlockCheck()        
        synapse.dendrite.hotkey = 'valid_hotkey'
        synapse.version = protocol.VERSION+1
        self.mock_metagraph.hotkeys = {'valid_hotkey'}
        self.mock_config.mode = 'prod'
        self.mock_miner_config.whitelisted_hotkeys = {'valid_hotkey'}
        self.mock_miner_config.blacklisted_hotkeys = set()

        result, message = base_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertIn("Blacklisted: Protocol Version differs", message)

    def test_base_blacklist_blacklisted_hotkey(self):
        synapse = protocol.BlockCheck()        
        synapse.dendrite.hotkey = 'blacklisted_hotkey'
        self.mock_metagraph.hotkeys = {'blacklisted_hotkey'}
        self.mock_miner_config.blacklisted_hotkeys = {'blacklisted_hotkey'}

        result, message = base_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Blacklisted hotkey: blacklisted_hotkey")

    def test_base_blacklist_not_whitelisted_hotkey(self):
        synapse = protocol.BlockCheck()        
        synapse.dendrite.hotkey = 'not_whitelisted_hotkey'
        self.mock_metagraph.hotkeys = {'not_whitelisted_hotkey'}
        self.mock_miner_config.whitelisted_hotkeys = set()
        self.mock_config.mode = 'prod'

        result, message = base_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Not Whitelisted hotkey: not_whitelisted_hotkey")

    def test_base_blacklist_recognized_hotkey(self):
        synapse = protocol.BlockCheck()        
        synapse.dendrite.hotkey = 'recognized_hotkey'
        self.mock_metagraph.hotkeys = {'recognized_hotkey'}
        self.mock_miner_config.whitelisted_hotkeys = {'recognized_hotkey'}

        result, message = base_blacklist(self.validator, synapse)
        self.assertFalse(result)
        self.assertEqual(message, "Hotkey recognized")

    def test_discovery_blacklist_base_blacklist_true(self):
        synapse = protocol.Discovery()        
        synapse.dendrite.hotkey = 'some_hotkey'
        base_blacklist_result = (True, "Base blacklist message")
        with patch('neurons.miners.blacklist.base_blacklist', return_value=base_blacklist_result):
            result, message = discovery_blacklist(self.validator, synapse)
        self.assertEqual(result, base_blacklist_result[0])
        self.assertEqual(message, base_blacklist_result[1])

    def test_discovery_blacklist_unregistered_hotkey(self):

        synapse = protocol.Discovery()        
        synapse.dendrite.hotkey = 'unregistered_hotkey'
        self.mock_metagraph.axons = []
        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False, '')):
            result, message = discovery_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Blacklisted a non registered hotkey's request from unregistered_hotkey")

    def test_discovery_blacklist_low_tao_stake(self):
        synapse = protocol.Discovery()        
        synapse.dendrite.hotkey = 'low_stake_hotkey'
        self.mock_metagraph.axons = [MagicMock(hotkey='low_stake_hotkey')]
        self.mock_metagraph.neurons = [MagicMock(stake=MagicMock(tao=5))]
        self.mock_miner_config.stake_threshold = 10
        self.mock_config.mode = 'prod'
        
        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False, '')):
            result, message = discovery_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Denied due to low stake: 5<10")

    def test_discovery_blacklist_request_rate_limiting(self):
        synapse = protocol.Discovery()        
        synapse.dendrite.hotkey = 'rate_limit_hotkey'
        self.mock_metagraph.axons = [MagicMock(hotkey='rate_limit_hotkey')]
        self.mock_metagraph.neurons = [MagicMock(stake=MagicMock(tao=15))]
        self.mock_miner_config.stake_threshold = 10
        self.mock_config.mode = 'prod'
        self.mock_miner_config.min_request_period = 60
        self.mock_miner_config.max_requests = 0
        self.validator.request_timestamps = {'rate_limit_hotkey': deque([time.time() - i for i in range(80,0)])}

        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False, '')):
            result, message = discovery_blacklist(self.validator, synapse)
        self.assertEqual(message, "Request rate exceeded for rate_limit_hotkey")
        self.assertTrue(result)

    def test_discovery_blacklist_hotkey_recognized(self):
        synapse = protocol.Discovery()        
        synapse.dendrite.hotkey = 'recognized_hotkey'
        self.mock_metagraph.axons = [MagicMock(hotkey='recognized_hotkey')]
        self.mock_metagraph.neurons = [MagicMock(stake=MagicMock(tao=15))]
        self.mock_miner_config.stake_threshold = 10
        self.mock_config.mode = 'prod'
        self.mock_miner_config.min_request_period = 60
        self.mock_miner_config.max_requests = 2
        self.validator.request_timestamps = {'recognized_hotkey': deque([time.time()])}

        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False, '')):
            result, message = discovery_blacklist(self.validator, synapse)

        self.assertEqual(message, "Hotkey recognized!")
        self.assertFalse(result)


    def test_query_blacklist_base_blacklist_true(self):
        synapse = protocol.Query()        
        synapse.dendrite.hotkey = 'some_hotkey'
        base_blacklist_result = (True, "Base blacklist message")
        with patch('neurons.miners.blacklist.base_blacklist', return_value=base_blacklist_result):
            result, message = query_blacklist(self.validator, synapse)
        self.assertEqual(result, base_blacklist_result[0])
        self.assertEqual(message, base_blacklist_result[1])

    def test_query_blacklist_network_mismatch(self):
        synapse = protocol.Query()        
        synapse.dendrite.hotkey = 'network_mismatch_hotkey'
        synapse.network = 'ethereum'
        self.mock_config.network = 'bitcoin'
        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False ,'')):
            result, message = query_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Network not supported.")

    def test_query_blacklist_model_type_mismatch(self):
        synapse = protocol.Query()        
        synapse.dendrite.hotkey = 'model_type_mismatch_hotkey'
        synapse.network = 'bitcoin'
        synapse.model_type = 'type2'
        self.mock_config.network = 'bitcoin'
        self.mock_config.model_type = 'type1'
        
        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False ,'')):
            result, message = query_blacklist(self.validator, synapse)
        self.assertTrue(result)
        self.assertEqual(message, "Model type not supported.")

    def test_query_blacklist_illegal_cypher_keywords(self):
        synapse = protocol.Query()        
        synapse.dendrite.hotkey = 'illegal_cypher_keywords_hotkey'
        synapse.network = 'bitcoin'
        synapse.model_type = 'type1'
        synapse.query = 'DROP CONSTRAINT'
        self.mock_config.network = 'bitcoin'

        self.mock_config.model_type = 'type1'
        with patch('neurons.miners.blacklist.base_blacklist', return_value=(False ,'')):
            result, message = query_blacklist(self.validator, synapse)
        self.assertEqual(message, "Illegal cypher keywords.")
        self.assertTrue(result)

    def test_query_blacklist_hotkey_recognized(self):
        synapse = protocol.Query()        
        synapse.dendrite.hotkey = 'recognized_hotkey'
        self.mock_config.network = 'bitcoin'
        self.mock_config.model_type = 'type1'
        synapse.network = 'bitcoin'
        synapse.model_type = 'type1'

        with patch('neurons.miners.blacklist.is_query_only', return_value=True):
            with patch('neurons.miners.blacklist.base_blacklist', return_value=(False ,'')):
                result, message = query_blacklist(self.validator, synapse)
        self.assertFalse(result)
        self.assertEqual(message, "Hotkey recognized!")
if __name__ == '__main__':
    unittest.main()