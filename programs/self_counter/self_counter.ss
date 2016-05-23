#SIMPLESCRIPT

SET $limit $argv[1]
SET $direction 1
SET $counter 0

L1  ADD $counter $counter $direction
    PRN "[SEND] Counter=" $counter
    SND $argv[0] $counter
    RCV $argv[0] $counter
    PRN "[RECV] Counter=" $counter

    SLP 1

    BGT $counter 0 L2
    MUL $direction $direction -1

L2  BLT $counter $limit L3
    MUL $direction $direction -1

L3  BRA L1
