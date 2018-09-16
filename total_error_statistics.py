import argparse
import os
import errno
import time


class ErrorAnalysisStatistics:
    def __init__(self):
        self.number_of_utterances_per_error = {}

        self.number_of_correction_not_contained_in_lattice = {}

        self.utterance_average_length = {'total': 0}

        self.utterances_per_error = {}
        
        self.all_errors_fixed_in_utterances_per_error = {}
        self.next_error_fixed_in_utt_per_error = {}
        self.next_error_NOT_fixed_in_utt_per_error = {}
        self.new_errors_added_in_utt_per_error = {}
        self.n_errors_fixed_in_utt_per_error = {}
        self.n_errors_NOT_fixed_in_utt_per_error = {}

        self.next_error_fixed_no_new_errors = {}
        self.next_error_fixed_no_new_errors_no_errors = {}

        self.next_error_fixed_new_errors = {}
        self.next_error_fixed_new_errors_no_errors = {}

        self.next_error_not_fixed_no_new_errors = {}
        self.next_error_not_fixed_no_new_errors_no_errors = {}

        self.next_error_not_fixed_new_errors = {}
        self.next_error_not_fixed_new_errors_no_errors = {}

        self.n_errors_fixed_no_new_errors = {}
        self.n_errors_fixed_no_new_errors_no_errors = {}

        self.n_errors_fixed_new_errors = {}
        self.n_errors_fixed_new_errors_no_errors = {}

        self.n_errors_not_fixed_no_new_errors = {}
        self.n_errors_not_fixed_no_new_errors_no_errors = {}

        self.n_errors_not_fixed_new_errors = {}
        self.n_errors_not_fixed_new_errors_no_errors = {}

        self.number_of_errors_added_before_second_error = {}

        self.words_not_in_lattice = {}

        self.words_next_error_not_fixed = {}
        self.words_next_error_not_fixed_arr = []


def init_references(reference_file, error_stats, isNew=False):
    """
    Creates reference file of utterances containing only specific number of errors
    :param      error_stats:
    :param      reference_file: perutt file containing all reference utterances and hypothesised recognition
    :return:    a list of all references with n_errors, a list of all hypotheses with n_errors and
                then a list of all other references and hypotheses
    """
    references = {}
    hypothesis = {}

    error_details = {}

    total_number_large_errors = 0
    large_errors_key = '15-32'

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
        elif info == '#csid':
            error_count = 0
            # the first number is the number of correct
            for error in range(1, len(utt_arr)):
                error_count += int(utt_arr[error])

            utt_length = len(references[utt_id].split())
            if error_count not in error_stats.number_of_utterances_per_error:
                error_stats.number_of_utterances_per_error[error_count] = 1
                error_stats.utterance_average_length[error_count] = utt_length
                error_stats.utterances_per_error[error_count] = {utt_id: references[utt_id]}
            else:
                error_stats.number_of_utterances_per_error[error_count] += 1
                error_stats.utterance_average_length[error_count] += utt_length
                error_stats.utterances_per_error[error_count][utt_id] = references[utt_id]

            if error_count >= 15:
                total_number_large_errors += 1
                if large_errors_key not in error_stats.utterance_average_length:
                    error_stats.utterance_average_length[large_errors_key] = utt_length
                else:
                    error_stats.utterance_average_length[large_errors_key] += utt_length

            error_stats.utterance_average_length['total'] += utt_length
        if info == 'op':
            # find the first n errors and error positions, this is only for results
            error_count = 0
            error_type = {}
            for i in range(len(utt_arr)):
                if utt_arr[i] != 'C':
                    if not isNew and error_count >= 1 and error_type[0][0] == 'I':
                        # Only check for this if we are looking at the original errors
                        error_type[error_count] = [utt_arr[i], i-1]
                    elif isNew:
                        # For easier comparison the new error starts at 1 not zero
                        error_type[error_count+1] = [utt_arr[i], i]
                    else:
                        error_type[error_count] = [utt_arr[i], i]
                    error_count += 1
            error_details[utt_id] = error_type

    compute_average_length(error_stats, len(references), total_number_large_errors)

    return references, hypothesis, error_details


def compute_average_length(error_stats, number_of_utterances, total_number_large_errors):
    for error in error_stats.number_of_utterances_per_error:
        error_stats.utterance_average_length[error] = error_stats.utterance_average_length[error] / error_stats.number_of_utterances_per_error[error]
    error_stats.utterance_average_length['total'] = error_stats.utterance_average_length['total'] / number_of_utterances
    error_stats.utterance_average_length['15-32'] = error_stats.utterance_average_length['15-32'] / total_number_large_errors
    return error_stats


def are_n_error_fixed(new_error_details, old_error_details):
    # check if every error in the old error details are fixed
    number_of_errors_not_fixed = 0
    for old_error in old_error_details:
        for new_error in new_error_details:
            if new_error_details[new_error] == old_error_details[old_error]:
                number_of_errors_not_fixed += 1
                break
    return True if number_of_errors_not_fixed == 0 else False


def is_next_error_fixed(new_error_details, next_error):
    for error in new_error_details:
        if new_error_details[error] == next_error:
            return False
    return True


def new_errors_added(new_error_details, old_error_details):
    """
    Checks if new error details contain new errors
    :param new_error_details:
    :param old_error_details:
    :return:
    """
    if len(new_error_details) > len(old_error_details):
        return True
    elif new_error_details == old_error_details:
        return False

    for new_error in new_error_details:
        is_new_error = True
        for old_error in old_error_details:
            if new_error_details[new_error] == old_error_details[old_error]:
                is_new_error = False
                break
        if is_new_error:
            # it is enough that one new error is added
            return True
    return False


def add_error(error_type, error, error_cnt_stats=None, error_cnt=0):
    if error not in error_type:
        error_type[error] = 1
    else:
        error_type[error] += 1

    if error_cnt_stats is not None:
        if error not in error_cnt_stats:
            error_cnt_stats[error] = error_cnt
        else:
            error_cnt_stats[error] += error_cnt


def error_analysis(error_stats, new_hypotheses, hypotheses, old_error_details, new_error_details):
    for error in error_stats.utterances_per_error:
        for utt_id in error_stats.utterances_per_error[error]:

            ref_arr = error_stats.utterances_per_error[error][utt_id].split()
            new_hyp_arr = new_hypotheses[utt_id].split()
            hyp_arr = hypotheses[utt_id].split()

            new_hyp_error_cnt = len(new_error_details[utt_id])

            # count all errors fixed
            if ref_arr == new_hyp_arr:
                add_error(error_stats.all_errors_fixed_in_utterances_per_error, error)

            # only check if the hypothesis was changed
            if ref_arr == new_hyp_arr and error > 1:
                add_error(error_stats.next_error_fixed_in_utt_per_error, error)

                add_error(error_stats.next_error_fixed_no_new_errors, error, error_stats.next_error_fixed_no_new_errors_no_errors, new_hyp_error_cnt)

                add_error(error_stats.n_errors_fixed_in_utt_per_error, error)

                add_error(error_stats.n_errors_fixed_no_new_errors, error, error_stats.n_errors_fixed_no_new_errors_no_errors, new_hyp_error_cnt)

            elif new_hyp_arr != hyp_arr:
                old_error_details[utt_id].pop(0, None)
                has_new_error = new_errors_added(new_error_details[utt_id], old_error_details[utt_id])
                if error > 1:
                    next_error_in_hyp = old_error_details[utt_id][1]
                    next_error_fixed = is_next_error_fixed(new_error_details[utt_id], next_error_in_hyp)
                    if error > 2:
                        n_errors_fixed = are_n_error_fixed(new_error_details[utt_id], old_error_details[utt_id])
                    else:
                        n_errors_fixed = True if next_error_fixed else False

                    # count is next error fixed
                    if next_error_fixed:
                        add_error(error_stats.next_error_fixed_in_utt_per_error, error)
                       # check if other errors are added
                        if has_new_error:
                            add_error(error_stats.next_error_fixed_new_errors, error, error_stats.next_error_fixed_new_errors_no_errors, new_hyp_error_cnt)
                        else:
                            add_error(error_stats.next_error_fixed_no_new_errors, error, error_stats.next_error_fixed_no_new_errors_no_errors, new_hyp_error_cnt)
                    else:
                        add_error(error_stats.next_error_NOT_fixed_in_utt_per_error, error)

                        # check if other errors are added
                        if has_new_error:
                            add_error(error_stats.next_error_not_fixed_new_errors, error, error_stats.next_error_not_fixed_new_errors_no_errors, new_hyp_error_cnt)
                        else:
                            add_error(error_stats.next_error_not_fixed_no_new_errors, error, error_stats.next_error_not_fixed_no_new_errors_no_errors, new_hyp_error_cnt)

                        # obtain the word at the error index in the reference that is not fixed
                        # if the reference is shorter than the error index, There is an insertion error at the end
                        if len(ref_arr)-1 >= next_error_in_hyp[1]:
                            error_stats.words_next_error_not_fixed_arr.append(ref_arr[next_error_in_hyp[1]])

                    # count if n errors are fixed
                    if n_errors_fixed:
                        add_error(error_stats.n_errors_fixed_in_utt_per_error, error)
                        # check if others were added
                        if has_new_error:
                            add_error(error_stats.n_errors_fixed_new_errors, error, error_stats.n_errors_fixed_new_errors_no_errors, new_hyp_error_cnt)
                        else:
                            add_error(error_stats.n_errors_fixed_no_new_errors, error, error_stats.n_errors_fixed_no_new_errors_no_errors, new_hyp_error_cnt)
                    else:
                        add_error(error_stats.n_errors_NOT_fixed_in_utt_per_error, error)
                        # check if others were added
                        if has_new_error:
                            add_error(error_stats.n_errors_not_fixed_new_errors, error, error_stats.n_errors_not_fixed_new_errors_no_errors, new_hyp_error_cnt)
                        else:
                            add_error(error_stats.n_errors_not_fixed_no_new_errors, error, error_stats.n_errors_not_fixed_no_new_errors_no_errors, new_hyp_error_cnt)

                if error > 1:
                    if check_if_error_added_before_next(new_error_details[utt_id], old_error_details[utt_id]):
                        add_error(error_stats.number_of_errors_added_before_second_error, error)

                # count if new errors are added
                compute_new_errors_added_stats(old_error_details[utt_id], new_error_details[utt_id], has_new_error, error_stats, error)
            elif new_hyp_arr == hyp_arr and ref_arr != hyp_arr:
                add_error(error_stats.number_of_correction_not_contained_in_lattice, error)
                # create a list of the words not presented in the lattices
                mismatch = find_correct_start(ref_arr, hyp_arr)
                if mismatch[1] not in error_stats.words_not_in_lattice:
                    error_stats.words_not_in_lattice[mismatch[1]] = 1
                else:
                    error_stats.words_not_in_lattice[mismatch[1]] += 1


def check_if_error_added_before_next(new_errors, old_errors):
    first_old_error = old_errors[1][1]
    for error in new_errors:
        if new_errors[error][1] < first_old_error:
            return True
    return False


def find_correct_start(reference, hypothesis):
    mismatch = (0, '')
    for i, word in zip(range(len(reference)), reference):
        if len(hypothesis) >= i + 1 and word != hypothesis[i]:
            # the words do not match
            mismatch = (i, word)
        elif len(hypothesis) < i + 1 and reference[:len(hypothesis)] == hypothesis:
            # the hypothesis is shorter than the reference, and everything matches up to the end
            # so the correct beginning is the hypothesis plus one
            mismatch = (i, reference[i])
    # if the hypothesis is longer than the reference,
    # and no error has been detected up to the end, the reference is returned
    return mismatch


def compute_new_errors_added_stats(old_error_details, new_error_details, has_new_error, error_stats, error):
    if len(old_error_details) > len(new_error_details):
        # if there are fewer errors in the new hyp, check if they are the same or if new were added
        if has_new_error:
            add_error(error_stats.new_errors_added_in_utt_per_error, error)
    elif len(old_error_details) < len(new_error_details):
        # if the error count in the new hyp is larger, new errors were definetely added
        add_error(error_stats.new_errors_added_in_utt_per_error, error)
    elif old_error_details != new_error_details:
        # if the error count is the same, check if the errors are the same
        add_error(error_stats.new_errors_added_in_utt_per_error, error)


def write_error_stats_to_file(filename, out_dir, error_stats):
    """
    Writes a dictionary of utterances to file
    :param error_stats:
    :param filename: name of file to write to
    :param out_dir: location of output folder
    """
    with open(out_dir + filename, 'w') as out_file:
        out_file.write('# errors per utt: ' + str(error_stats.number_of_utterances_per_error) + '\n\n')
        out_file.write('# all errors fixed, per error: ' + str(error_stats.all_errors_fixed_in_utterances_per_error) + '\n\n')
        out_file.write('# next error also fixed, per error: ' + str(error_stats.next_error_fixed_in_utt_per_error) + '\n\n')
        out_file.write('# next error NOT fixed, per error: ' + str(error_stats.next_error_NOT_fixed_in_utt_per_error) + '\n\n')
        out_file.write('# n errors fixed, per error: ' + str(error_stats.n_errors_fixed_in_utt_per_error) + '\n\n')
        out_file.write('# n errors NOT fixed, per error: ' + str(error_stats.n_errors_NOT_fixed_in_utt_per_error) + '\n\n')
        out_file.write('# new errors added, per error: ' + str(error_stats.new_errors_added_in_utt_per_error) + '\n\n')
        out_file.write('# new errors added between first and second error, per error: ' + str(error_stats.number_of_errors_added_before_second_error) + '\n\n')
        out_file.write('# average length, per error, in words: ' + str(error_stats.utterance_average_length) + '\n\n')
        out_file.write('# correction not contained in lattice: ' + str(error_stats.number_of_correction_not_contained_in_lattice) + '\n\n')
        out_file.write('\n---Is next error fixed---\n')
        out_file.write('# Second error fixed and no new errors added:  ' + str(error_stats.next_error_fixed_no_new_errors) + '\n')
        out_file.write('# Second error fixed and no new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.next_error_fixed_no_new_errors_no_errors) + '\n\n')

        out_file.write('# Second error fixed and new errors added:  ' + str(error_stats.next_error_fixed_new_errors) + '\n')
        out_file.write('# Second error fixed and new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.next_error_fixed_new_errors_no_errors) + '\n\n')

        out_file.write('# Second error NOT fixed and no new errors added:  ' + str(error_stats.next_error_not_fixed_no_new_errors) + '\n')
        out_file.write('# Second error NOT fixed and no new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.next_error_not_fixed_no_new_errors_no_errors) + '\n\n')

        out_file.write('# Second error NOT fixed and new errors added:  ' + str(error_stats.next_error_not_fixed_new_errors) + '\n')
        out_file.write('# Second error NOT fixed and new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.next_error_not_fixed_new_errors_no_errors) + '\n\n')
        out_file.write('\n---Are n errors fixed---\n')
        out_file.write('# n errors fixed and no new errors added:  ' + str(error_stats.n_errors_fixed_no_new_errors) + '\n')
        out_file.write('# n errors fixed and no new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.n_errors_fixed_no_new_errors_no_errors) + '\n\n')

        out_file.write('# n errors fixed and new errors added:  ' + str(error_stats.n_errors_fixed_new_errors) + '\n')
        out_file.write('# n errors fixed and new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.n_errors_fixed_new_errors_no_errors) + '\n\n')

        out_file.write('# n errors NOT fixed and no new errors added:  ' + str(error_stats.n_errors_not_fixed_no_new_errors) + '\n')
        out_file.write('# n errors NOT fixed and no new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.n_errors_not_fixed_no_new_errors_no_errors) + '\n\n')

        out_file.write('# n errors NOT fixed and new errors added:  ' + str(error_stats.n_errors_not_fixed_new_errors) + '\n')
        out_file.write('# n errors NOT fixed and new errors added TOTAL ERRORS REMAINING:  ' + str(error_stats.n_errors_not_fixed_new_errors_no_errors) + '\n\n')

    # oov_filename = out_dir + 'next_error_not_fixed_words_array'
    # with open(oov_filename, 'w') as out_file:
    #     # out_file.write('words when next error is not fixed: ' + str(error_stats.words_next_error_not_fixed) + '\n\n')
    #     for word in error_stats.words_next_error_not_fixed_arr:
    #         out_file.write(word + '\n')


def parse_args():
    parser = argparse.ArgumentParser(description='Best path in lattices',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('r', type=argparse.FileType('r'), help='Reference file')
    parser.add_argument('w', type=argparse.FileType('r'), help='New Reference file')
    parser.add_argument('-o', type=str, default='kaldi_new_best_path', help='Output directory')
    parser.add_argument('-n', type=str, default=0, help='Number of errors to look at')

    return parser.parse_args()


def main():
    args = parse_args()
    reference_file = args.r
    new_reference_file = args.w

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

    error_stats = ErrorAnalysisStatistics()

    references, hypothesis, old_error_details = init_references(reference_file, error_stats)

    new_error_stats = ErrorAnalysisStatistics()

    new_references, new_hypothesis, new_error_details = init_references(new_reference_file, new_error_stats, True)

    error_analysis(error_stats, new_hypothesis, hypothesis, old_error_details, new_error_details)

    filename = 'error-results-' + time.strftime('%d-%b-') + time.strftime('%H:%M') + '.txt'
    write_error_stats_to_file(filename, out_dir, error_stats)


if __name__ == '__main__':
    main()
