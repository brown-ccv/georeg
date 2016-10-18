import nltk
import re
import csv
import os
from Levenshtein import distance

import exceptions

# takes in text then returns tokens as a list of strings (without occurences!)
def tokenize(text, min_len=2, allow_number_tokens=False):

    # remove as much punctuation as can be safely done
    # (note: $ and @ are left out because they can be confused with letters by the OCR)
    text = re.sub("[\[\](){}'~\".,/\\|&^*%#!<>?;:]", "", text)
    tokens = re.split("[\t \n_-]", text)

    if allow_number_tokens:
        filter = lambda t: len(t) >= min_len
    else:
        filter = lambda t: len(t) >= min_len and not t.isdigit()

    tokens = [t.lower() for t in tokens if filter(t)]

    return tokens

def ratio(str1, str2):
    """
    Custom ratio function,
    This implementation is more logical
    than implementation Levenshtein gives
    :return: similarity ratio as a percent
    """
    #return (1.0 - distance(str1, str2) * 1.0 / (len(str1) + len(str2))) * 100.0
    try:
        return (1.0 - distance(unicode(str1), unicode(str2)) * 1.0 / max(len(str1), len(str2))) * 100.0
    except exceptions.TypeError:
        print type(str1), type(str2)
        raise

class Token(object): # a "word" in our spellcheck dictionary
    def __init__(self, value = "", count = 0):
        self.count = count
        self.value = value

        self.similar_tokens = set([])

    def touched_by(self, id):
        try:
            if id == self._touch_id: return True
            else: return False
        except AttributeError:
            return False

    def touch_with(self, id):
        self._touch_id = id

    def remove_touch_id(self):
        try:
            del self._touch_id
        except AttributeError:
            pass


class SpellChecker(object):
    def __init__(self, similarity_thresh = 50):
        self._tokens = {}
        self._total_occurrences = 0 # the sum of all tokens' count members
        self.__next_touch_id = 0

        # this should not be changed manually (our dictionary will require reprocessing)
        self.__similarity_thresh = similarity_thresh

    def _next_touch_id(self):
        """only for use by search functions"""
        self.__next_touch_id = (self.__next_touch_id + 1) % 5000
        return self.__next_touch_id

    @property
    def words(self):
        return self._tokens.iterkeys()
    @property
    def words_with_count(self):
        return ((t.value,t.count) for t in self._tokens.itervalues())

    def load_dictionary_from_tsv(self, file_name):
        """This will throw a RuntimeError if the dictionary is corrupt"""
        self._tokens = {} # free memory
        file_name = os.path.splitext(file_name)[0] + ".tsv" # force extension to .tsv

        try:
            with open(file_name, "r") as file:
                file_reader = csv.reader(file, delimiter="\t")

                self.__similarity_thresh, self._total_occurrences = file_reader.next()

                self.__similarity_thresh = int(self.__similarity_thresh)
                self._total_occurrences = int(self._total_occurrences)

                # read in file and record similar token lists as strings
                for row in file_reader:
                    new_token = Token(row[0], int(row[1]))

                    for item in row[2:]:
                        new_token.similar_tokens.add(item)

                    self._tokens[new_token.value] = new_token

            # replace string values with actual token objects
            for token in self._tokens.itervalues():
                token.similar_tokens = set([self._tokens[t] for t in token.similar_tokens])

        except (IndexError, KeyError):
            e = RuntimeError("dictionary file \"%s\" seems to be corrupt" % file_name)
            raise e

    def write_dictionary_to_tsv(self, file_name):

        # force extension to .tsv
        file_name = os.path.splitext(file_name)[0] + ".tsv"

        with open(file_name, "w") as file:
            file_writer = csv.writer(file, delimiter="\t")

            # write general member attributes
            file_writer.writerow([self.__similarity_thresh, self._total_occurrences])

            # record tokens
            for token in self._tokens.itervalues():
                file_writer.writerow([token.value, token.count] + [t.value for t in token.similar_tokens])


    def get_best_spelling_correction_slow(self, token_str, target_similarity = 100):
        """perform a slow lookup, only for benchmarking purposes"""
        if token_str in self._tokens:
            return token_str, 100

        best_score = 0
        best_token = None

        for known_token in self._tokens.itervalues():
            sim_score = ratio(token_str, known_token.value)

            if sim_score > best_score:
                best_token = known_token
                best_score = sim_score

                if best_score >= target_similarity:
                    break

        return best_token.value, best_score

    def get_best_spelling_correction(self, token_str, target_similarity=80):
        """
        Finds the most likely match to token_str in our dictionary,
        if token_str matches a token in our dictionary verbatim it will skip
        the fuzzy match search and just return the existing match
        :param token_str: the string to be matched
        :param target_similarity: a similarity score that will stop the search once reached,
               if less than __similarity_thresh then stops after first recursive search
        :return: a tuple with the match and score as a percent i.e. (match, score)
        """

        if token_str in self._tokens:
            return token_str, 100

        touch_id = self._next_touch_id()

        best_score = 0
        best_token = None

        for known_token in self._tokens.itervalues():
            sim_score = ratio(token_str, known_token.value)

            if sim_score >= self.__similarity_thresh:
                most_similar_token, overall_score = self.__find_most_similar_token(token_str, known_token, touch_id,
                                                                                   sim_score)
                if overall_score > best_score:
                    best_token = most_similar_token
                    best_score = overall_score

                    if best_score >= target_similarity:
                        break
        if best_token is not None:
            best_token_str = best_token.value
        else:
            best_token_str = token_str

        return best_token_str, best_score

    def change_similarity_threshold(self, new_sim_thresh):
        """rebuilds the dictionary with the new similarity threshold"""

        # update our similar tokens lists
        if new_sim_thresh < self.__similarity_thresh:
            for token1 in self._tokens.itervalues():
                for token2 in self._tokens.itervalues():
                    if self.__similarity_thresh > ratio(token1.value, token2.value) >= new_sim_thresh:
                        token1.similar_tokens.add(token2)
                        token2.similar_tokens.add(token1)
        elif new_sim_thresh > self.__similarity_thresh:
            for token in self._tokens.itervalues():
                # new similar token list for 'token' (the list can't be change while we iterate through it)
                new_sim_set = set([])

                for sim_token in token.similar_tokens:
                    # see if the similar tokens still pass the threshold
                    if ratio(token.value, sim_token.value) >= new_sim_thresh: # if they do add them to the new list
                        new_sim_set.add(sim_token)
                    else:
                        sim_token.similar_tokens.discard(token) # if they don't remove this token from the other token's similar token list
                token.similar_tokens = new_sim_set

        self.__similarity_thresh = new_sim_thresh

    def remove_all_tokens(self):
        self._tokens = {}
        self._total_occurrences = 0
        self.__next_touch_id = 0

    def add_common_tokens_from_txt_file(self, fn, num=1000, start=0):
        with open(fn,"r") as file:
            txt = file.read()
            self.add_common_tokens_from_txt(txt, num, start)

    def add_common_tokens_from_txt(self, text, num=1000, start=0):
        """
        finds most common tokens in provided text and adds them to dictionary
        :param text: text to get tokens from
        :param num: number of common tokens to add
        :param start: number of common tokens to skip starting from most common
                      (i.e. 10 would mean ignore the ten most common tokens)
        :return:
        """
        tokens = tokenize(text)

        freq_dist = nltk.FreqDist(tokens)
        tokens = freq_dist.most_common(num + start)

        # crop out from starting pos
        tokens = tokens[start:]

        for token_str, count in tokens:
            self.add_token(token_str, count)

    def add_token(self, token_str, token_count):
        """
        Add a token to the spell checker's dictionary
        :param token_str: the token's string
        :param token_count: the number of times this token has been found in our
                            target text (this represents its frequency of occurrence)
        :return: no return
        """

        if token_str in self._tokens:
            self._tokens[token_str].count += token_count
            return

        new_token = Token(token_str, token_count)

        # update our similar tokens lists
        for existing_token in self._tokens.itervalues():
            if ratio(new_token.value, existing_token.value) >= self.__similarity_thresh:
                new_token.similar_tokens.add(existing_token)
                existing_token.similar_tokens.add(new_token)

        self._total_occurrences += token_count
        self._tokens[token_str] = new_token

    def __find_most_similar_token(self, token_str, similar_token, touch_id, sim_score):
        """
        Searches for the token with spelling closest to token_str starting from similar_token
        then calls __proximity_search_for_most_likely_match to find the token with the best
        overall match score (similarity * frequency)
        :param token_str: string of token to be matched to
        :param similar_token: a token to start the search from, is assumed to have a high similarity score with token_str
        :param sim_score: the similarity score between token_str and similar_token
        :param touch_tag: the touch tag to be used for this search operation
        :return: (best_token, best_overall_score)
        """

        best_similarity_score = sim_score
        best_token = similar_token

        better_token_found = True

        while better_token_found:
            better_token_found = False

            for token in best_token.similar_tokens:
                if not token.touched_by(touch_id):
                    token.touch_with(touch_id)
                else:
                    continue

                similarity_score = ratio(token_str, token.value)

                if similarity_score > best_similarity_score:
                    best_similarity_score = similarity_score
                    best_token = token
                    better_token_found = True

        return best_token, best_similarity_score

# spell_checker = SpellChecker(similarity_thresh=50)
#
# # spell_checker.load_dictionary_from_tsv("texas_vocab")
#
# txt_corpi = []
#
# for item in os.listdir("./Texas dumps"):
#     with open(os.path.join("./Texas dumps", item), "r") as file:
#         txt_corpi.append(file.read())
#
# txt_corpi = "\n".join(txt_corpi)
#
# spell_checker.add_common_tokens_from_txt(txt_corpi, 3000)
# spell_checker.write_dictionary_to_tsv("texas_vocab_50.tsv")
#
# spell_checker.change_similarity_threshhold(new_sim_thresh=55)
# spell_checker.write_dictionary_to_tsv("texas_vocab_55.tsv")
#
# spell_checker.change_similarity_threshhold(new_sim_thresh=60)
# spell_checker.write_dictionary_to_tsv("texas_vocab_60.tsv")
