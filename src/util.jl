# just to avoid magical constants in code
const CODON_LENGTH = 3

const BASES = DNASeq("ACGT")
const BASEINTS = Dict(DNA_A => 1, DNA_C => 2, DNA_G => 3, DNA_T => 4)


"""LogSumExp in base 10.

Borrowed from StatsFuns.jl.
"""
function logsumexp10{T<:Real}(x::AbstractArray{T})
    S = typeof(exp10(zero(T)))    # because of 0.4.0
    isempty(x) && return -S(Inf)
    u = maximum(x)
    abs(u) == Inf && return any(isnan, x) ? S(NaN) : u
    s = zero(S)
    for i = 1:length(x)
        @inbounds s += exp10(x[i] - u)
    end
    log10(s) + u
end


@generated function summax(a, b)
    return quote
        result = a[1] + b[1]
        for i = 2:min(length(a), length(b))
            result = max(result, a[i] + b[i])
        end
        return result
    end
end