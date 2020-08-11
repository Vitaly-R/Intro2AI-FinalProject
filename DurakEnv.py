from DurakPlayer import DurakPlayer
from HumanPlayer import HumanPlayer
from typing import List, Tuple, Union, Optional
from Deck import Deck
from GUI import GUI
import random


class DurakEnv:

    MIN_PLAYERS = 2
    MAX_PLAYERS = 6
    HAND_SIZE = 6

    CardListType = List[Deck.CardType]
    StateType = Tuple[CardListType, CardListType, CardListType, CardListType]
    NumberType = Union[int, float]
    InfoType = List

    def __init__(self, players: List[DurakPlayer], render=False):
        # non-changing parameters:
        self.players = players
        self.to_render = render or (True in [isinstance(player, HumanPlayer) for player in players])
        self.attacker = 0
        self.defender = 1
        # changing parameters (will be re-initialized upon calling the reset method):
        self.active_players = players
        self.attacking_player = None
        self.turn_player = None
        self.loser = None
        self.attacking_cards = list()
        self.defending_cards = list()
        self.legal_attacking_cards = list()
        self.legal_defending_cards = list()
        self.state = (self.attacking_cards, self.defending_cards, self.legal_attacking_cards, self.legal_defending_cards)
        self.gui = GUI() if self.to_render else None
        self.deck = Deck()
        self.trump_suit = self.deck.HEARTS
        self.defending = True
        self.successful = False
        self.limit = 0
        self.last_action = Deck.NO_CARD
        self.reset_round = False
        self.attack_phase = True
        self.reset_attacker = True
        self.reward = 0
        self.first_initialize_players()

    def first_initialize_players(self):
        for player in self.players:
            player.set_trump_suit(self.trump_suit)

    def reset(self) -> StateType:
        self.active_players = self.players[:]
        random.shuffle(self.active_players)
        self.attacking_player = None
        self.turn_player = None
        self.loser = None
        self.attacking_cards = list()
        self.defending_cards = list()
        self.legal_attacking_cards = list()
        self.legal_defending_cards = list()
        self.state = (self.attacking_cards, self.defending_cards, self.legal_attacking_cards, self.legal_defending_cards)
        self.gui = GUI() if self.to_render else None
        self.deck = Deck()
        self.trump_suit = self.deck.HEARTS
        self.defending = True
        self.successful = False
        self.limit = 0
        self.last_action = Deck.NO_CARD
        self.reset_round = False
        self.attack_phase = True
        self.reset_attacker = True
        self.reward = 0
        self.initialize_players()
        self.set_first_attacker()
        self.do_reset_round()
        self.update_legal_cards()
        return self.state[0][:], self.state[1][:], self.state[2][:], self.state[3][:]

    def initialize_players(self):
        for player in self.active_players:
            player.set_gui(self.gui)
            player.initialize_for_game()
        deal = True
        while deal:
            self.initialize_deck()
            self.reset_hands()
            deal = self.deal_cards()

    def initialize_deck(self):
        self.deck = Deck()
        self.deck.shuffle()

    def reset_hands(self):
        for player in self.active_players:
            player.empty_hand()
            player.set_trump_suit(self.trump_suit)

    def deal_cards(self):
        for player in self.active_players:
            drawn_cards = self.deck.draw(self.HAND_SIZE)
            player.take_cards(drawn_cards)
            if not player.is_starting_hand_legal():
                return True
        return False

    def set_first_attacker(self):
        lowest_trump_value = self.deck.ACE + 1
        starting_player_name = None
        for player in self.active_players:
            value = player.get_lowest_trump()
            if value < lowest_trump_value:
                lowest_trump_value = value
                starting_player_name = player.name
        if starting_player_name is not None:
            while self.active_players[self.attacker].name != starting_player_name:
                temp = self.active_players.pop(self.attacker)
                self.active_players.append(temp)

    def step(self, action) -> Tuple[StateType, NumberType, bool, InfoType]:
        self.last_action = action
        self.reward = 0
        if self.attack_phase:
            self.do_attack_phase()
        else:
            self.do_defence_phase()
        self.reward = self.calculate_reward()
        self.check_end_round()
        if self.reset_round:
            self.update_end_round_players()
            self.update_players_hands()
            self.remove_winners()
            self.update_active_players_order()
            if not self.game_over():
                self.do_reset_round()
        self.update_legal_cards()
        self.dispose_events()
        return (self.state[0][:], self.state[1][:], self.state[2][:], self.state[3][:]), self.reward, self.game_over(), list()

    def do_attack_phase(self):
        if self.last_action != self.deck.NO_CARD:
            self.attacking_cards.append(self.last_action)
            self.attack_phase = False
        else:
            if self.turn_player == self.active_players[-1]:
                self.defending = False
                self.successful = True
                self.reset_attacker = True
            else:
                self.reset_attacker = False
                self.turn_player = self.active_players[self.active_players.index(self.turn_player) + 1]
                if self.turn_player == self.active_players[self.defender]:
                    if self.turn_player != self.active_players[-1]:
                        self.turn_player = self.active_players[self.active_players.index(self.turn_player) + 1]
                    else:
                        self.turn_player = self.active_players[self.active_players.index(self.turn_player) - 1]
                        self.defending = False
                        self.successful = True
                        self.reset_attacker = True

    def do_defence_phase(self):
        if self.last_action != self.deck.NO_CARD:
            self.defending_cards.append(self.last_action)
            self.attack_phase = True
            if len(self.attacking_cards) == len(self.defending_cards) == self.limit:
                # successful defence
                self.defending = False
                self.successful = True
            self.reset_attacker = True
        else:
            self.defending = False
            self.successful = False
            self.turn_player.take_cards(self.attacking_cards)
            self.turn_player.take_cards(self.defending_cards)

    def update_players_hands(self):
        for player in self.active_players[:self.defender] + self.active_players[self.defender + 1:]:
            drawn_cards = self.deck.draw(max(0, self.HAND_SIZE - player.hand_size))
            player.take_cards(drawn_cards)
        drawn_cards = self.deck.draw(max(0, self.HAND_SIZE - self.active_players[self.defender].hand_size))
        self.active_players[self.defender].take_cards(drawn_cards)

    def remove_winners(self):
        to_remove = list()
        for player in self.active_players:
            if player.hand_size == 0:
                to_remove.append(player)
        for player in to_remove:
            self.active_players.remove(player)

    def update_active_players_order(self):
        if len(self.active_players) == 1:
            self.loser = self.active_players[0]
        elif len(self.active_players) >= self.MIN_PLAYERS:
            if self.active_players[self.attacker] == self.attacking_player:
                self.move_attacker_back()
            if not self.successful:
                self.move_attacker_back()

    def move_attacker_back(self) -> None:
        """
        Moves the current attacker to the end of the active players list.
        """
        temp = self.active_players.pop(self.attacker)
        self.active_players.append(temp)

    def do_reset_round(self):
        self.attacking_cards = list()
        self.defending_cards = list()
        self.legal_attacking_cards = list()
        self.legal_defending_cards = list()
        self.state = (self.attacking_cards, self.defending_cards, self.legal_attacking_cards, self.legal_defending_cards)
        self.turn_player = self.active_players[self.attacker]
        self.attacking_player = self.active_players[self.attacker]
        self.defending = True
        self.successful = False
        self.limit = min(self.HAND_SIZE, self.active_players[self.defender].hand_size)
        self.attack_phase = True
        self.reset_attacker = True
        self.reset_round = False

    def update_legal_cards(self):
        self.legal_attacking_cards = list()
        self.legal_defending_cards = list()
        if len(self.attacking_cards) == 0:
            self.legal_attacking_cards = self.deck.get_full_list_of_cards()
            self.legal_defending_cards = [Deck.NO_CARD]
        else:
            self.legal_attacking_cards = [self.deck.NO_CARD]
            self.legal_defending_cards = [self.deck.NO_CARD]
            for card in self.deck.get_full_list_of_cards():
                if card not in self.attacking_cards and card not in self.defending_cards:
                    for a_card in self.attacking_cards:
                        if card[0] == a_card[0] and card[1] != a_card[1]:
                            self.legal_attacking_cards.append(card)
                            break
                    if card not in self.legal_attacking_cards:
                        for d_card in self.defending_cards:
                            if card[0] == d_card[0] and card[1] != d_card[1]:
                                self.legal_attacking_cards.append(card)
                                break
                if len(self.attacking_cards) > len(self.defending_cards):
                    if card not in self.defending_cards:
                        if (card[1] == self.attacking_cards[-1][1] and card[0] > self.attacking_cards[-1][0]) or \
                                ((card[1] == self.trump_suit) and (self.attacking_cards[-1][1] != self.trump_suit)):
                            self.legal_defending_cards.append(card)
        self.state = (self.attacking_cards, self.defending_cards, self.legal_attacking_cards, self.legal_defending_cards)

    def dispose_events(self):
        self.gui.dispose_events() if self.gui is not None else None

    def calculate_average_change(self, for_trump=False):
        final_sum = 0
        suits = [self.trump_suit] if for_trump else self.turn_player.get_others_suit
        for suit in suits:
            old_values = [card[0] for card in self.turn_player.last_hand if card[1] == suit]
            old = 0 if len(old_values) == 0 else sum(old_values) / len(old_values)
            new_values = [card[0] for card in self.turn_player.hand if card[1] == suit]
            curr = 0 if len(new_values) == 0 else sum(new_values) / len(new_values)
            final_sum += (curr - old)
        return final_sum

    def difference_in_trump_cards(self):
        return len([c for c in self.turn_player.hand if c[1] == self.trump_suit]) - \
               len([c for c in self.turn_player.last_hand if c[1] == self.trump_suit])

    def calculate_reward(self):
        # suits_avg_change = self.calculate_average_change(for_trump=False) / 27
        # trumps_avg_change = self.calculate_average_change(for_trump=True) / 9
        # diff_in_trump_cards = self.difference_in_trump_cards() / 9

        # small reward on success defense
        # neg reward on taking cards
        if not self.turn_player.hand_size and not self.deck.current_num_cards:
            return 30

        if not self.defending:
            if self.successful:
                return 1
            else:
                return -1

        return 0

        # sum_all = (0.4 * suits_avg_change + 0.6 * (trumps_avg_change * 0.4 + diff_in_trump_cards * 0.6)) * 100
        # if self.turn_player.hand_size == 0:
        #     sum_all += 1000

    def check_end_round(self):
        if not self.defending:
            self.reset_round = True
        else:
            if self.attack_phase and self.reset_attacker:
                self.turn_player = self.active_players[self.attacker]
            elif not self.attack_phase:
                self.turn_player = self.active_players[self.defender]

    def update_end_round_players(self):
        for player in self.active_players:
            player.update_end_round(self.active_players[self.defender].name, (self.attacking_cards, self.defending_cards), self.successful)

    def render(self):
        if self.to_render and self.gui is not None:
            attacker = self.active_players[self.attacker] if len(self.active_players) else None
            defender = self.active_players[self.defender] if len(self.active_players) >= self.MIN_PLAYERS else None
            self.gui.show_screen(self.players, (self.attacking_cards, self.defending_cards),
                                 attacker, defender,
                                 self.deck, self.trump_suit)

    def game_over(self):
        return len(self.active_players) < self.MIN_PLAYERS

    def get_turn_player(self) -> Optional[DurakPlayer]:
        return self.turn_player

    def to_attack(self) -> bool:
        return self.attack_phase

    def end_gui(self):
        self.gui.end() if self.gui is not None else None

    def get_loser(self):
        return self.loser

    def get_available_actions(self):
        """
        The available actions are chosen by checking whether or not the player is attacking, and then taking the legal attacking/defending cards
        of the player
        :return: The available actions (cards) of the player. empty set if no available actions found
        """
        if self.turn_player == self.active_players[self.defender]:
            return set(self.turn_player.hand).intersection(set(self.state[3]))
        return set(self.turn_player.hand).intersection(set(self.state[2]))
