from DurakPlayer import Deck, Tuple, List, Optional, DurakPlayer
from PPONetwork import PPONetwork
import joblib
import numpy as np
import os
import itertools


class PPOPlayer(DurakPlayer):

    output_dim = len(Deck.get_full_list_of_cards()) + 1
    input_dim = 185  # hand, attacking cards, defending cards, memory and legal cards to play

    def __init__(self, hand_size: int, name: str, training_network=None, sess=None):
        super().__init__(hand_size, name)
        self.memory = []
        self.last_converted_state = None
        self.last_converted_available_cards = None

        self.value = 0
        self.neglogpac = 0

        if training_network:
            self.test_phase = False
            self.training_network = training_network  # this will be done in the training phase
        else:
            self.test_phase = True
            # load the network from memory, and use it for interpretation (not training)
            self.training_network = PPONetwork(sess, self.input_dim, self.output_dim, "testNet")

            # find latest model parameters file
            files = [(int(f[5:]), f) for f in os.listdir(os.curdir + '/PPOParams') if f.find('model') != -1]
            files.sort(key=lambda x: x[0])
            latest_file = files[-1][1]
            params = joblib.load(os.curdir + '/PPOParams/' + latest_file)
            self.training_network.loadParams(params)

    def update_end_round(self, defending_player_name: str, table: Tuple[List[Deck.CardType], List[Deck.CardType]],
                         successfully_defended: bool) -> None:
        if successfully_defended:
            # update memory to include cards
            for card in itertools.chain(table[0], table[1]):
                self.memory.append(card)
        else:
            # You can save the memory for each player separately here. We chose not to.
            pass

    def attack(self, table: Tuple[List[Deck.CardType], List[Deck.CardType]],
               legal_cards_to_play: List[Deck.CardType]) -> Optional[Deck.CardType]:

        converted_state = self.convert_input((self.hand, table[0], table[1], self.memory, legal_cards_to_play))
        self.last_converted_state = converted_state
        converted_available_cards = self.convert_available_cards(legal_cards_to_play)
        self.last_converted_available_cards = converted_available_cards
        action, self.value, self.neglogpac = self.training_network.step(converted_state, converted_available_cards)
        action = Deck.get_card_from_index(action[0])
        if action != Deck.NO_CARD:
            self._hand.remove(action)
        else:
            action = Deck.NO_CARD

        if self.test_phase:
            return action
        return action

    def defend(self, table: Tuple[List[Deck.CardType], List[Deck.CardType]],
               legal_cards_to_play: List[Deck.CardType]) -> Optional[Deck.CardType]:

        converted_state = self.convert_input((self.hand, table[0], table[1], self.memory, legal_cards_to_play))
        self.last_converted_state = converted_state
        converted_available_cards = self.convert_available_cards(legal_cards_to_play)
        self.last_converted_available_cards = converted_available_cards
        action, self.value, self.neglogpac = self.training_network.step(converted_state, converted_available_cards)
        action = Deck.get_card_from_index(action[0])
        if action != Deck.NO_CARD:
            self._hand.remove(action)

        if self.test_phase:
            return action
        return action

    def get_val_neglogpac(self):
        return self.value, self.neglogpac

    def convert_input(self, input):
        # the input contains: hand, attacking_cards, defending_cards, memory, legal_cards_to_play
        deck_length = len(Deck.get_full_list_of_cards()) + 1  # +1 for NO CARD
        converted_state = np.zeros(shape=(1, deck_length * len(input)))
        for i in range(len(input)):
            for card in input[i]:
                card_idx = Deck.get_index_from_card(card)
                converted_state[0][deck_length * i + card_idx] = 1

        return converted_state

    def convert_available_cards(self, legal_cards_to_play):
        deck_length = len(Deck.get_full_list_of_cards()) + 1  # +1 for NO CARD
        converted_available_cards = np.full(shape=(1, deck_length), fill_value=-np.inf)
        for card in legal_cards_to_play:
            card_idx = Deck.get_index_from_card(card)
            converted_available_cards[0][card_idx] = 0
        return converted_available_cards

    def initialize_for_game(self):
        super().initialize_for_game()
        self.memory = []


def from_path(sess, hand_size, name, path) -> PPOPlayer:
    """
    Loads a PPOPlayer using the parameters from the file whose path is given as an input.
    If the loading fails, a player with an untrained network will be returned.
    :param sess: tensorflow session
    :param hand_size: size of starting hand for the player
    :param name: name of the player
    :param path: path of the parameters file
    :return: a PPOPlayer with parameters from the given file. If loading fails, a non-trained PPOPlayer
    """
    network = PPONetwork(sess, PPOPlayer.input_dim, PPOPlayer.output_dim, name + "_Network")
    try:
        parameters = joblib.load(path)
        network.loadParams(parameters)
        player = PPOPlayer(hand_size, name, network, sess)
        player.test_phase = True
        return player
    except:
        player = PPOPlayer(hand_size, name, network, sess)
        return player
