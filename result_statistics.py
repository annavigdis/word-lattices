import argparse
import os
import errno
import time

from pathlib import Path


class ErrorAnalysisStatistics:
    def __init__(self):

        self.all_errors_fixed_new_errors = 0
        self.all_errors_fixed_no_new_errors = 0
        self.all_errors_not_fixed_no_new_errors = 0
        self.all_errors_not_fixed_new_errors = 0

        # The correction word is not in the lattice
        self.number_of_hypothesis_not_corrected = 0

        # Keep track of the words not in the lattice
        self.words_not_in_path = {}

        self.new_hypotheses_with_ref_and_old_hyp = {}


def created_other_errors(start, end, ref, new_hyp):
    created_new_errors = False
    if ref[start:end] != new_hyp[start:end] or ref[end+1:] != new_hyp[end+1:]:
        created_new_errors = True
    return created_new_errors


def init_references_with_n_errors(reference_file, n_errors=None):
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

    replace_symbol = '***'

    for line in reference_file.readlines():
        utt_id, info, *utt_arr = line.split()

        if utt_id == 'BjÓ-rad20160408T112521_00004':
            print()

        if info == 'ref':
            # remove insertion symbols from ref to be able to match the original reference from nbest
            utt = ' '.join(utt_arr).replace(replace_symbol, '')
            all_other_references[utt_id] = utt.strip()
        elif info == 'hyp':
            # remove insertion symbols from hyp to be able to match the original reference from nbest
            utt = ' '.join(utt_arr).replace(replace_symbol, '')
            all_other_hypothesis[utt_id] = utt.strip()
        elif info == '#csid' and n_errors is not None:
            error_count = 0
            # the first number is the number of correct
            for error in range(1, len(utt_arr)):
                error_count += int(utt_arr[error])
            if error_count == n_errors:
                n_error_references[utt_id] = all_other_references[utt_id]
                n_error_hypothesis[utt_id] = all_other_hypothesis[utt_id]
                all_other_references.pop(utt_id, None)
                all_other_hypothesis.pop(utt_id, None)
        if info == 'op':
            # find the first n errors and error positions, this is only for results
            error_count = 1
            error_type = {}
            for i in range(len(utt_arr)):
                if utt_arr[i] != 'C':
                    if error_count > 1:
                        # Only check for this if we are looking at the original errors
                        if error_type[1][0] == 'I' and n_errors is not None:
                            error_type[error_count] = [utt_arr[i], i-1]
                        else:
                            error_type[error_count] = [utt_arr[i], i]
                    else:
                        error_type[error_count] = [utt_arr[i], i]
                    error_count += 1
            error_details[utt_id] = error_type

    if n_errors is not None:
        return n_error_references, n_error_hypothesis, error_details
    else:
        return all_other_references, all_other_hypothesis, error_details


def write_error_stats(stats, number_of_errors):
    print('------- error stats for ' + str(number_of_errors) + 'errors')
    print('All errors fixed, no new errors added:', stats.all_errors_fixed_no_new_errors)
    print('All errors fixed, new errors added', stats.all_errors_fixed_new_errors)
    print('All errors NOT fixed, no new errors added', stats.all_errors_not_fixed_no_new_errors)
    print('All errors NOT fixed, new errors added', stats.all_errors_not_fixed_new_errors)
    print('Number of hypothesis not corrected: ', stats.number_of_hypothesis_not_corrected)


def error_analysis(references, new_hypothesis, hypothesis, old_error_details, new_error_details, number_of_errors):
    stats = ErrorAnalysisStatistics()

    for utt_id in references:
        ref = references[utt_id].split()
        hyp = hypothesis[utt_id].split()
        new_hyp = new_hypothesis[utt_id].split()
        if ref == new_hyp:
            stats.all_errors_fixed_no_new_errors += 1
        elif new_hyp == hyp:
            # the new hypothesis remains the same because
            # the correct word was not in the lattice
            stats.number_of_hypothesis_not_corrected += 1
        else:
            # compare the errors
            if number_of_errors == 2:
                stats = compare_2_errors_utt(stats, old_error_details[utt_id], new_error_details[utt_id], utt_id, ref, hyp, new_hyp)
            else:
                stats = compare_3_errors_utt(stats, old_error_details[utt_id], new_error_details[utt_id], utt_id, ref, hyp, new_hyp)

    write_error_stats(stats, number_of_errors)


def compare_2_errors_utt(stats, old_error_details, new_error_details, utt_id, reference, hypothesis, new_hypothesis):
    # remove the first error
    updated_old_error_details = {1: old_error_details[2]}
    if updated_old_error_details == new_error_details:
        # no errors added, no errors fixed
        stats.all_errors_not_fixed_no_new_errors += 1
    elif len(new_error_details) > len(updated_old_error_details):
        # Go through all the error and check if one of the remains the same
        same_error_count = 0
        for error in new_error_details:
            if new_error_details[error] == updated_old_error_details[1]:
                same_error_count += 1
        # if the error count is not 0 then the errors were fixed but new errors were introduced
        if same_error_count == 0:
            stats.all_errors_fixed_new_errors += 1
        else:
            stats.all_errors_not_fixed_new_errors += 1
    else:
        # the new error does not match either the old errors
        # but is not error free, so new errors have been introduced
        stats.all_errors_fixed_new_errors += 1

    return stats


def compare_3_errors_utt(stats, old_error_details, new_error_details, utt_id, reference, hypothesis, new_hypothesis):
    # remove the first errors
    updated_old_error_details = {1: old_error_details[2], 2: old_error_details[3]}
    if updated_old_error_details == new_error_details:
        # no errors added, no errors fixed
        stats.all_errors_not_fixed_no_new_errors += 1
    elif len(new_error_details) < len(updated_old_error_details):
        # there is only one error
        if new_error_details[1] == updated_old_error_details[1] or new_error_details[1] == updated_old_error_details[2]:
            stats.all_errors_not_fixed_no_new_errors += 1
        else:
            # the new error does not match either the old errors
            # but is not error free, so new errors have been introduced
            stats.all_errors_fixed_new_errors += 1
    elif len(new_error_details) > len(updated_old_error_details):
        error_count = 0
        for error in new_error_details:
            if new_error_details[error] == updated_old_error_details[1] or new_error_details[error] == updated_old_error_details[2]:
                error_count += 1
        # if the error count is not 0 then the errors were fixed but and new errors were introduced
        if error_count == 0:
            stats.all_errors_fixed_new_errors += 1
        else:
            stats.all_errors_not_fixed_new_errors += 1
    else:
        # the error count is the same
        error_count = 0
        for error in new_error_details:
            if new_error_details[error] == updated_old_error_details[1] or new_error_details[error] == updated_old_error_details[2]:
                error_count += 1
        if error_count == 0:
            stats.all_errors_fixed_new_errors += 1
        elif error_count == 2:
            stats.all_errors_not_fixed_no_new_errors += 1
        else:
            stats.all_errors_not_fixed_new_errors += 1

    return stats


def parse_args():
    parser = argparse.ArgumentParser(description='Best path in lattices',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('r', type=argparse.FileType('r'), help='Reference file')
    parser.add_argument('w', type=argparse.FileType('r'), help='New Reference file')
    parser.add_argument('-o', type=str, default='kaldi_new_best_path', help='Output directory')
    parser.add_argument('-n', type=str, default=1, help='Number of errors to look at')

    return parser.parse_args()


def trim_error_details(reference, error_details):
    trimmed_error_details = {}
    for key in error_details:
        if key in reference:
            trimmed_error_details[key] = error_details[key]
    return trimmed_error_details


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

    number_of_errors = int(args.n)

    references, hypothesis, old_error_details = init_references_with_n_errors(reference_file, number_of_errors)
    old_error_details = trim_error_details(references, old_error_details)
    new_references, new_hypothesis, new_error_details = init_references_with_n_errors(new_reference_file, None)
    new_error_details = trim_error_details(new_references, new_error_details)

    error_analysis(references, new_hypothesis, hypothesis, old_error_details, new_error_details, number_of_errors)


if __name__ == '__main__':
    main()
