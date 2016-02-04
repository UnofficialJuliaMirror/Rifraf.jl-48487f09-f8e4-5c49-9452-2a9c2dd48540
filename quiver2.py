import random

import numpy as np

# TODO: do not completely recompute As and Bs each iteration. Only recompute from (first) Acol on.
# TODO: implement banding.
# TODO: either write slow code in Cython, or rewrite in Julia
# TODO: compress duplicate reads and account for their scores


def update(arr, i, j, s_base, t_base, log_p, log_ins, log_del):
    return max([arr[i - 1, j] + log_ins,  # insertion
                arr[i, j - 1] + log_del,  # deletion
                # TODO: log(1-p) may not be negligible
                arr[i - 1, j - 1] + (0 if s_base == t_base else log_p)])


def forward(s, log_p, t, log_ins, log_del):
    result = np.zeros((len(s) + 1, len(t) + 1))
    result[:, 0] = log_ins * np.arange(len(s) + 1)
    result[0, :] = log_del * np.arange(len(t) + 1)
    for i in range(1, len(s) + 1):
        for j in range(1, len(t) + 1):
            result[i, j] = update(result, i, j, s[i-1], t[j-1], log_p[i-1], log_ins, log_del)
    return result


def backward(s, log_p, t, log_ins, log_del):
    s = list(reversed(s))
    log_p = list(reversed(log_p))
    t = list(reversed(t))
    return np.flipud(np.fliplr(forward(s, log_p, t, log_ins, log_del)))


def mutations(template):
    """Returns (function, position, base)"""
    for j in range(len(template)):
        for base in 'ACGT':
            if template[j] == base:
                continue
            yield [substitution, j, base]
        yield [deletion, j, None]
        for base in 'ACGT':
            yield [insertion, j, base]
    # insertion after last
    for base in 'ACGT':
        yield [insertion, len(template), base]


def substitution(mutation, template, seq, log_p, A, B, log_ins, log_del):
    mtype, pos, base = mutation
    Acols = np.copy(A[:, pos:pos+2])
    j = 1
    for i in range(1, A.shape[0]):
        Acols[i, j] = update(Acols, i, j, seq[i-1], base, log_p[i-1], log_ins, log_del)
    if pos == len(template) - 1:
        return Acols[:, 1], None
    return Acols[:, 1], B[:, pos + 1]


def deletion(mutation, template, seq, log_p, A, B, log_ins, log_del):
    _, pos, _ = mutation
    if pos == len(template) - 1:
        return A[:, -2], None
    Acols = np.zeros((A.shape[0], 2))
    Acols[:, 0] = A[:, pos]
    Acols[0, 1] = Acols[0, 0] + log_del
    mybase = template[pos + 1]
    j = 1
    for i in range(1, A.shape[0]):
        Acols[i, j] = update(Acols, i, j, seq[i-1], mybase, log_p[i-1], log_ins, log_del)
    return Acols[:, 0], B[:, pos + 1]


def insertion(mutation, template, seq, log_p, A, B, log_ins, log_del):
    _, pos, base = mutation
    Acols = np.zeros((A.shape[0], 2))
    Acols[:, 0] = A[:, pos]
    Acols[0, :] = Acols[0, 0] + np.arange(2) * log_del
    j = 1
    for i in range(1, A.shape[0]):
        Acols[i, j] = update(Acols, i, j, seq[i-1], base, log_p[i-1], log_ins, log_del)
    if pos == len(template):
        return Acols[:, 1], None
    return Acols[:, 1], B[:, pos]


def score_mutation(mutation, template, seq, log_p, A, B, log_ins, log_del):
    """Score a mutation using the forward-backward trick."""
    f, _, _ = mutation
    Acol, Bcol = f(mutation, template, seq, log_p, A, B, log_ins, log_del)
    if Bcol is None:
        return Acol[-1]
    return (Acol + Bcol).max()


def update_template(template, mutation):
    f, pos, base = mutation
    if f == substitution:
        return ''.join([template[:pos], base, template[pos + 1:]])
    elif f == insertion:
        return ''.join([template[:pos], base, template[pos:]])
    elif f == deletion:
        return ''.join([template[:pos], template[pos + 1:]])
    else:
        raise Exception('unknown mutation: {}'.format(mtype))


def apply_mutations(template, mutations):
    for i in range(len(mutations)):
        score, mutation = mutations[i]
        template = update_template(template, mutation)
        f, pos, _ = mutation
        if f == insertion:
            for ii in range(i + 1, len(mutations)):
                if mutations[ii][1][1] > pos:
                    mutations[ii][1][1] += 1
        elif f == deletion:
            for ii in range(i + 1, len(mutations)):
                if mutations[ii][1][1] > pos:
                    mutations[ii][1][1] -= 1
    return template


def choose_candidates(candidates, min_dist, i, max_multi_iters):
    final_cands = []
    if i < max_multi_iters:
        posns = set()
        for c in reversed(sorted(candidates, key=lambda c: c[0])):
            _, (_, posn, _) = c
            if any(abs(posn - p) < min_dist for p in posns):
                continue
            posns.add(posn)
            final_cands.append(c)
    else:
        final_cands = [list(sorted(candidates, key=lambda c: c[0]))[-1]]
    return final_cands


def quiver2(sequences, phreds, log_ins, log_del, min_dist=9,
            max_iters=100, max_multi_iters=50, seed=None,
            verbose=False):
    """
    sequences: list of dna sequences

    phreds: list of numpy array

    """
    log_ps = list(-phred / 10 for phred in phreds)
    # TODO: use pbdagcon for initial template
    state = np.random.RandomState(seed)
    template = state.choice(sequences)

    As = list(forward(s, p, template, log_ins, log_del) for s, p in zip(sequences, log_ps))
    Bs = list(backward(s, p, template, log_ins, log_del) for s, p in zip(sequences, log_ps))
    cur_score = sum(A[-1, -1] for A in As)
    for i in range(max_iters):
        if verbose:
            print("iteration {}".format(i))
        candidates = []
        for mutation in mutations(template):
            score = sum(score_mutation(mutation, template, seq, log_p, A, B, log_ins, log_del)
                        for seq, log_p, A, B in zip(sequences, log_ps, As, Bs))
            if score > cur_score:
                candidates.append([score, mutation])
        if not candidates:
            break
        chosen_cands = choose_candidates(candidates, min_dist, i, max_multi_iters)
        template = apply_mutations(template, chosen_cands)
        As = list(forward(s, p, template, log_ins, log_del) for s, p in zip(sequences, log_ps))
        Bs = list(backward(s, p, template, log_ins, log_del) for s, p in zip(sequences, log_ps))
        cur_score = sum(A[-1, -1] for A in As)
        if verbose:
            print('  kept {} mutations'.format(len(chosen_cands)))
            print('  score: {}'.format(cur_score))
    return template
