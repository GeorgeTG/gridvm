#SIMPLESCRIPT

ADD $nxt $argv[0] 1
MOD $nxt $nxt $argv[1]
SUB $prv $argv[0] 1
MOD $prv $prv $argv[1]

BGT $argv[0] 0 L1
SET $cnt 0
SND $nxt $cnt

L1 RCV $prv $cnt
   SLP 1
   ADD $cnt $cnt 1
   BGE $cnt $argv[2] L2
   SND $nxt $cnt
   BRA L1

L2 RET
