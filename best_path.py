import argparse
import os
import errno
import time

from pathlib import Path

INF = float('Inf')
NBEST_HYPOTHESIS_FILENAME = '/words_text.txt'


class GraphStatistics:
    def __init__(self):
        self.correct_paths = {}
        self.correct_path_words = []
        self.correction_not_in_fst = {}
        self.new_hyp = {}
        self.old_hyp = {}

    def add_to_correct_paths(self, cost, path, edge):
        new_path = path + [edge]
        self.correct_paths[edge] = (new_path, cost)


def init_graph(lattice):
    graph = {}
    start = -1
    end = -1
    is_start = True
    for line in lattice:
        info = line.split()
        if len(info) == 4:
            _start_state, _end_state, word, transition_id = info
            acoustic_cost, graph_cost, ids = transition_id.split(',')
            acoustic_cost = float(acoustic_cost)
            graph_cost = float(graph_cost)
            if _start_state in graph:
                graph[_start_state].append((_end_state, acoustic_cost + graph_cost, str(word)))
            else:
                graph[_start_state] = [(_end_state, acoustic_cost + graph_cost, str(word))]

            if is_start:
                start = _start_state
                is_start = False
        else:
            # at the end state
            end = info[0]
            graph[info[0]] = [(info[0], 0.0)]

    return graph, start, end


def find_best_path(hypothesis, lattice, reference):
    graph, start, end = init_graph(lattice)

    graph_info = GraphStatistics()

    mismatch, correct_start = find_correct_start(reference.split(), hypothesis.split())

    if len(correct_start) != 0:
        find_path_with_correct_start(correct_start, graph, start, end, graph_info, '', 0.0)
        new_hypothesis = construct_new_hypothesis(hypothesis, graph, end, graph_info, correct_start)
    else:
        new_hypothesis = hypothesis

    return new_hypothesis


def construct_new_hypothesis(hypothesis, graph, end, graph_info, correct_start):
    if len(graph_info.correct_paths) == 0:
        return hypothesis
    else:
        hypothesized_end = find_shortest_paths_among_possible_paths(graph_info.correct_paths, graph, end)
        new_hypothesis = ''
        for word in correct_start:
            new_hypothesis += word if len(new_hypothesis) == 0 else ' ' + word
        new_hypothesis += ' ' + hypothesized_end
        return new_hypothesis


def find_shortest_paths_among_possible_paths(paths, graph, end):
    """

    :param paths:
    :param graph:
    :param end:
    :return:
    """
    shortest_path = []
    shortest_path_cost = INF
    shortest_path_start_state = '0'
    for edge in paths:
        distance, came_from = bellman_ford_search(graph, edge)
        path_cost = paths[edge][1] + distance[end]

        # tmp_path, tmp_new_hypothesis = reconstruct_path(came_from, edge, end, graph)
        # print(tmp_new_hypothesis, path_cost)

        if path_cost < shortest_path_cost:
            shortest_path_cost = path_cost
            shortest_path = came_from
            shortest_path_start_state = edge
    best_path, test_new_hypothesis = reconstruct_path(shortest_path, shortest_path_start_state, end, graph)
    return test_new_hypothesis


def find_path_with_correct_start(correct_start, graph, start, end, graph_info, words_so_far, cost_so_far, path=[],
                                 words='', cost=0.0):
    tmp_path = path + [start]
    words += words_so_far
    cost += cost_so_far
    if start == end:
        return [tmp_path], words, cost
    if start not in graph:
        return [], '', 0.0
    paths = []
    words_arr = ''
    total_cost = 0.0
    for node in graph[start]:
        if node[0] not in tmp_path:
            # if node is not in the path find all paths from the node to the end state
            path_words = '' if node[2] == '<eps>' else ' ' + node[2]
            tmp_words = words + path_words
            words_so_far = tmp_words.split()

            path_cost = node[1]
            cost_so_far = cost + path_cost

            if correct_start == words_so_far:
                graph_info.add_to_correct_paths(cost_so_far, tmp_path, node[0])
                graph_info.correct_path_words = words_so_far
                continue
            if correct_start[:len(words_so_far)] != words_so_far:
                continue
            else:
                path = tmp_path

            new_paths, words_arr, total_cost = find_path_with_correct_start(correct_start, graph, node[0], end,
                                                                            graph_info, path_words, path_cost, path,
                                                                            words, cost)

            for newpath in new_paths:
                paths.append(newpath)

    return paths, words_arr, total_cost


def find_correct_utterance_start(reference, mismatch):
    """

    :param reference:
    :param mismatch:
    :return:
    """
    # remove all hypothesis from n best list that don't match that beginning plus the next word
    if len(reference) >= mismatch[0]:
        correct_start = reference[:mismatch[0] + 1]
    else:
        correct_start = reference[:mismatch[0]]
    return correct_start


def find_correct_start(reference, hypothesis):
    mismatch = (0, '')
    correct_start = reference
    for i, word in zip(range(len(reference)), reference):
        if len(hypothesis) >= i + 1 and word != hypothesis[i]:
            # the words do not match
            mismatch = (i, word)
            correct_start = find_correct_utterance_start(reference, mismatch)
            break
        elif len(hypothesis) < i + 1 and reference[:len(hypothesis)] == hypothesis:
            # the hypothesis is shorter than the reference, and everything matches up to the end
            # so the correct beginning is the hypothesis plus one
            mismatch = (i, reference[i])
            correct_start = reference[:len(hypothesis) + 1]
            break
    # if the hypothesis is longer than the reference,
    # and no error has been detected up to the end, the reference is returned
    return mismatch, correct_start


def created_other_errors(start, end, ref, new_hyp):
    created_new_errors = False
    if ref[start:end] != new_hyp[start:end] or ref[end+1:] != new_hyp[end+1:]:
        created_new_errors = True
    return created_new_errors


def find_new_hypotheses(references, hypotheses, lattices):
    new_hypotheses_method_applied_to = {}
    old_hypotheses_method_applied_to = {}
    new_hypotheses = {}

    for utt_id in lattices:
        if " ".join(references[utt_id].split()) != " ".join(hypotheses[utt_id].split()):
            new_hypothesis = find_best_path(hypotheses[utt_id], lattices[utt_id], references[utt_id])
            new_hypotheses[utt_id] = new_hypothesis
            if new_hypothesis.split() != hypotheses[utt_id].split():
                new_hypotheses_method_applied_to[utt_id] = new_hypothesis
                old_hypotheses_method_applied_to[utt_id] = hypotheses[utt_id]
        else:
            new_hypotheses[utt_id] = hypotheses[utt_id]

    return new_hypotheses, new_hypotheses_method_applied_to, old_hypotheses_method_applied_to


def get_utterance_words(path, graph):
    words = ''
    for i in range(0, len(path)):
        if path[i] == path[-1]:
            break
        else:
            start_state = path[i]
            end_state = path[i + 1]
            count = 0
            for edge in graph[start_state]:
                if edge[0] == end_state:
                    count += 1
                    # This is possible because the states are ordered
                    # So if two or more states are identical the first state
                    # in the graph file is always the state with the lowest cost
                    if edge[2] != '<eps>' and count < 2:
                        words += edge[2] if len(words) == 0 else ' ' + edge[2]
    return words


def get_words(path, wfst):
    words = ''
    for i in range(0, len(path)):
        if path[i] == path[-1]:
            break
        else:
            start_state = path[i]
            end_state = path[i + 1]
            count = 0
            for state in wfst:
                if state[0] == int(start_state) and state[1] == int(end_state):
                    count += 1
                    # This is possible because the states are ordered
                    # So if two or more states are identical the first state
                    # in the fsts file is always the state with the lowest cost
                    if state[2] != '<eps>' and count < 2:
                        words += state[2] if len(words) == 0 else ' ' + state[2]
    return words


def reconstruct_path(came_from, start, goal, graph):
    path = []
    current = goal
    while current != start and current is not None:
        path.append(current)
        current = came_from[current]
    path.append(start)
    path.reverse()
    words = get_utterance_words(path, graph)
    return path, words


def bellman_ford_search(graph, start):
    """
    Bellman ford shortest path algorithm, do not checks if the graph has negative cycles
    Classic implementation, checks every edge at each iteration
    :param      graph: a weighted graph that contains no negative cycles
    :param      start: a vertex, which will be the starting destination of the search
    :return:    distance: a dictionary of the cost of each vertex in the shortest path
                predecessor: a dictionary of all predecessor of vertices in the shortest path
    """
    distance = {}
    predecessor = {}

    # Initialize the graph
    for node in graph:
        # all vertices have a weight of infinity except the first node
        distance[node] = 0 if node == start else INF
        predecessor[node] = None

    # Relax edges repeatedly, n-1 times
    for i in range(len(graph)):
        if str(i) in graph:
            node = graph[str(i)]
            # Iterate over every edge
            # examine each node one by one and all of its outgoing edges
            # guaranteed to have looked at all of the edges when this is done
            for edge in node:
                # Apply Ford's rule (relax) if possible
                weight = edge[1]
                if distance[str(i)] + weight < distance[edge[0]]:
                    distance[edge[0]] = distance[str(i)] + weight
                    predecessor[edge[0]] = str(i)

    return distance, predecessor


def combine_fst_files(lattice_input):
    print(lattice_input)
    p = Path(lattice_input)
    lattice_list = []
    if p.is_dir():
        for arch in p.iterdir():
            q = str(arch)
            print(q)
            with open(q) as f:
                lattice_list += f.readlines()
    else:
        with open(str(lattice_input)) as f:
            lattice_list += f.readlines()
    return lattice_list


def init_lattices(lattice_file):
    lattice_list = combine_fst_files(lattice_file)
    lattices = {}
    first = True
    utt_id = None
    for line in lattice_list:
        if line == '\n':
            first = True
            continue
        if first:
            utt_id = line.strip()
            first = False
        else:
            if utt_id in lattices:
                lattices[utt_id].append(line.strip())
            else:
                lattices[utt_id] = [line.strip()]
    return lattices


def init_references(reference_file):
    references = {}
    hypothesis = {}
    error_details = {}
    for line in reference_file.readlines():
        utt_id, info, *utt_arr = line.split()

        if info == 'ref':
            # remove insertion symbols from ref to be able to match the original reference from nbest
            utt = ' '.join(utt_arr).replace('***', '')
            references[utt_id] = utt.strip()
        elif info == 'hyp':
            # remove insertion symbols from hyp to be able to match the original reference from nbest
            utt = ' '.join(utt_arr).replace('***', '')
            hypothesis[utt_id] = utt.strip()
        if info == 'op':
            # find the first error and error positions, this is only for results
            error_type = {}
            error_count = 0
            for i in range(len(utt_arr)):
                if utt_arr[i] != 'C':
                    error_type[error_count] = [utt_arr[i], i]
                    error_count += 1
            error_details[utt_id] = error_type
        else:
            continue

    return references, hypothesis, error_details


def init_references_n_or_more_errors(reference_file, n_error, find_n_or_more=False):
    """
    Creates reference file of utterances containing only specific number of errors
    :param      reference_file: perutt file containing all reference utterances and hypothesised recognition
    :param      n_errors: the number of errors per utterance you want to have in your new reference file
    :return:    a list of all references with n_errors, a list of all hypotheses with n_errors and
                then a list of all other references and hypotheses
    """
    all_other_references = {}
    all_other_hypothesis = {}

    n_error_references = {}
    n_error_hypothesis = {}

    error_details = {}

    for line in reference_file.readlines():
        utt_id, info, *utt_arr = line.split()

        if info == 'ref':
            # remove insertion symbols from ref to be able to match the original reference from nbest
            utt = ' '.join(utt_arr).replace('***', '')
            all_other_references[utt_id] = utt.strip()
        elif info == 'hyp':
            # remove insertion symbols from hyp to be able to match the original reference from nbest
            utt = ' '.join(utt_arr).replace('***', '')
            all_other_hypothesis[utt_id] = utt.strip()
        elif info == '#csid':
            error_count = 0
            # the first number is the number of correct
            for error in range(1, len(utt_arr)):
                error_count += int(utt_arr[error])
            if find_n_or_more:
                if error_count >= n_error:
                    n_error_references[utt_id] = all_other_references[utt_id]
                    n_error_hypothesis[utt_id] = all_other_hypothesis[utt_id]
                    all_other_references.pop(utt_id, None)
                    all_other_hypothesis.pop(utt_id, None)
            else:
                if error_count == n_error:
                    n_error_references[utt_id] = all_other_references[utt_id]
                    n_error_hypothesis[utt_id] = all_other_hypothesis[utt_id]
                    all_other_references.pop(utt_id, None)
                    all_other_hypothesis.pop(utt_id, None)
        if info == 'op':
            # find the first error and error positions, this is only for results
            error_type = {}
            error_count = 0
            for i in range(len(utt_arr)):
                if utt_arr[i] != 'C':
                    error_type[error_count] = [utt_arr[i], i]
                    error_count += 1
            error_details[utt_id] = error_type

    return n_error_references, n_error_hypothesis, error_details


def init_lattices_with_n_errors(lattice_file, references_n_errors):
    """
    Creates a list of lattices that all have a specific number of errors
    :param lattice_file: a file containing word FST or an folder containing an archive of word FST files
    :param references_n_errors: specifies the number of errors per utterance you want to have in your new lattice file
    :return: a list of all lattices containing n_errors
    """
    lattice_list = combine_fst_files(lattice_file)
    lattices_with_n_errors = {}
    first = True
    utt_id = None
    cnt = 0
    for line in lattice_list:
        if line == '\n':
            first = True
            continue
        if first:
            utt_id = line.strip()
            first = False
        else:
            if utt_id in references_n_errors:
                cnt += 1
                if utt_id in lattices_with_n_errors:
                    lattices_with_n_errors[utt_id].append(line.strip())
                else:
                    lattices_with_n_errors[utt_id] = [line.strip()]
    return lattices_with_n_errors


def write_utterances_to_file(filename, out_dir, utterances):
    """
    Writes a dictionary of utterances to file
    :param filename: name of file to write to
    :param out_dir: location of output folder
    :param utterances: a dictionary of utterances
    """
    with open(out_dir + filename, 'w') as out_file:
        for key in sorted(utterances.keys()):
            value = utterances[key]
            if isinstance(value, str):
                out_file.write(key + ' ' + value + '\n')
            else:
                out_file.write(key + ' ' + value[0] + '\n')


def create_new_hypothesises_and_reference_files_with_n_errors(references_with_n_errors, hypothesis_with_n_errors,
                                                              lattice_file, number_of_errors, out_dir):
    lattices = init_lattices_with_n_errors(lattice_file, references_with_n_errors)

    new_hypotheses, applied_to_new, applied_to_old = find_new_hypotheses(references_with_n_errors, hypothesis_with_n_errors, lattices)

    combined_hypotheses_file_name = 'new_hypotheses_' + str(number_of_errors) + '_errors.txt'
    reference_file_name = 'references_' + str(number_of_errors) + '_errors.txt'
    old_hypotheses_file_name = 'old_hypotheses_' + str(number_of_errors) + '_errors.txt'

    applied_to_new_filename = 'applied_to_new_' + str(number_of_errors) + '_errors.txt'
    applied_to_old_filename = 'applied_to_old_' + str(number_of_errors) + '_errors.txt'
    write_utterances_to_file(applied_to_new_filename, out_dir, applied_to_new)
    write_utterances_to_file(applied_to_old_filename, out_dir, applied_to_old)

    # write the references with n errors to file
    write_utterances_to_file(combined_hypotheses_file_name, out_dir, new_hypotheses)

    # write the new hypothesised utterances to file
    write_utterances_to_file(reference_file_name, out_dir, references_with_n_errors)

    # write the old hypothesised utterances to file
    write_utterances_to_file(old_hypotheses_file_name, out_dir, hypothesis_with_n_errors)


def write_new_hypothesis(error_details, mismatch, hypothesis):
    if error_details[0][0] == 'S':
        # If substitution error, replace the word
        hypothesis[mismatch[0]] = mismatch[1]
        new_hypothesis = ' '.join(hypothesis)
    elif error_details[0][0] == 'I':
        # If insertion, remove the word
        hypothesis.pop(mismatch[0])
        new_hypothesis = ' '.join(hypothesis)
    else:
        # If deletion error, add the word
        hypothesis.insert(mismatch[0], mismatch[1])
        new_hypothesis = ' '.join(hypothesis)
    return new_hypothesis


def fix_first_error(references, hypotheses, error_details, lattice_file, filename, out_dir, only_utt_method_is_applied_to=False):
    first_error_fixed_hypotheses = {}

    lattices = init_lattices_with_n_errors(lattice_file, references)
    new_hypotheses, applied_to_new, applied_to_old = find_new_hypotheses(references, hypotheses, lattices)

    for utt_id in references:
        reference = references[utt_id].split()
        hypothesis = hypotheses[utt_id].split()

        if reference == hypothesis:
            first_error_fixed_hypotheses[utt_id] = hypotheses[utt_id]
            continue

        mismatch, correct_start = find_correct_start(reference, hypothesis)

        if new_hypotheses[utt_id].split() != hypothesis:
            first_error_fixed_hypotheses[utt_id] = write_new_hypothesis(error_details[utt_id], mismatch, hypothesis)
        elif not only_utt_method_is_applied_to and new_hypotheses[utt_id].split() == hypothesis:
            first_error_fixed_hypotheses[utt_id] = hypotheses[utt_id]

    write_utterances_to_file(filename, out_dir, first_error_fixed_hypotheses)

    return first_error_fixed_hypotheses


def create_new_hypothesises_and_reference_files(references, hypotheses, lattice_file, out_dir, subset=False):
    if subset:
        lattices = init_lattices_with_n_errors(lattice_file, references)
    else:
        lattices = init_lattices(lattice_file)

    new_hypotheses, applied_to_new, applied_to_old = find_new_hypotheses(references, hypotheses, lattices)

    result_file_name = 'new_hypotheses.txt'
    reference_file_name = 'references.txt'
    old_hypotheses_file_name = 'old_hypotheses.txt'

    if subset:
        result_file_name = 'new_hypotheses_one_or_more_errors.txt'
        reference_file_name = 'references_one_or_more_errors.txt'
        old_hypotheses_file_name = 'old_hypotheses_one_or_more_errors.txt'
        applied_to_new_filename = 'applied_to_new_one_or_more_errors.txt'
        applied_to_old_filename = 'applied_to_old_one_or_more_errors.txt'
        write_utterances_to_file(applied_to_new_filename, out_dir, applied_to_new)
        write_utterances_to_file(applied_to_old_filename, out_dir, applied_to_old)

    # write the references with n errors to file
    write_utterances_to_file(result_file_name, out_dir, new_hypotheses)

    # write the new hypothesised utterances to file
    write_utterances_to_file(reference_file_name, out_dir, references)

    # write the old hypothesised utterances to file
    write_utterances_to_file(old_hypotheses_file_name, out_dir, hypotheses)


def parse_args():
    parser = argparse.ArgumentParser(description='Best path in lattices',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('r', type=argparse.FileType('r'), help='Reference file')
    parser.add_argument('w', type=str, help='Kaldi word lattice file or OR a directory of archives of word lattices')
    parser.add_argument('-o', type=str, default='kaldi_new_best_path', help='Output directory')
    parser.add_argument('-n', type=str, default=0, help='Number of errors to look at')

    return parser.parse_args()


def main():
    # Takes as an input a word lattice or an archive of word lattices.
    # Then takes the number of errors specified in the input and creates and uses the per utt file to find only the
    # utterances with the specific number of errors.
    # Those utterances are taken and a new best path is found through the correction of the first error each utterance

    # r: Location of the per utt file that is used as a reference
    # w: a word lattice file or a directory of archived word lattices
    # - o: the output directory for the new lattices
    # - n: the number of errors to look at. So if 4 is given the script will find all lattices with error count equal to 4 and find a new path through those lattices

    args = parse_args()
    reference_file = args.r
    lattice_file = args.w

    if args.o == 'new_nbest':
        out_dir = args.o + '_' + time.strftime("%Y%m%d-%H%M%S") + '/'
    else:
        out_dir = args.o
        if not out_dir.endswith('/'):
            out_dir += '/'

    # allow to overwrite existing directory
    try:
        os.mkdir(out_dir)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        pass

    number_of_errors = int(args.n)

    if number_of_errors == 0:
        references, hypotheses, error_details = init_references(reference_file)
        create_new_hypothesises_and_reference_files(references, hypotheses, lattice_file, out_dir)
    else:
        references_with_n_errors, hypotheses_with_n_errors, error_details = init_references_n_or_more_errors(reference_file, number_of_errors)
        create_new_hypothesises_and_reference_files_with_n_errors(references_with_n_errors, hypotheses_with_n_errors,
                                                                  lattice_file, number_of_errors, out_dir)


if __name__ == '__main__':
    main()
