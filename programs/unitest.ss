#SIMPLESCRIPT

   PRN "A"
   PRN "AbBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvXxYyZz1234567890!@#$%^&*()+-=/?><:;"
   SET $val_a 1
   SET $val_b 2
   SET $val_c 3
   PRN "val_a " $val_a
   PRN "val_a & val_b " $val_a $val_b
   PRN "val_a & val_b & val_c " $val_a $val_b $val_c 

   PRN "argv[0] & argc " $argv[0] $argc  

   SET $testcnt 0

   ADD $testcnt $testcnt 1
   SET $res 1
   BGT $res 0 L1 
   PRN "FAILURE TEST " $testcnt $res

L1 ADD $testcnt $testcnt 1
   SET $res 1
   BGE $res 1 L2 
   PRN "FAILURE TEST " $testcnt $res

L2 ADD $testcnt $testcnt 1
   SET $res 1
   BLT $res 2 L3 
   PRN "FAILURE TEST " $testcnt $res

L3 ADD $testcnt $testcnt 1
   SET $res 1
   BLE $res 1 L4 
   PRN "FAILURE TEST " $testcnt $res

L4 ADD $testcnt $testcnt 1
   SET $res 1
   BEQ $res 1 L5 
   PRN "FAILURE TEST " $testcnt $res

L5 ADD $testcnt $testcnt 1
   BRA  L6 
   PRN "FAILURE TEST " $testcnt $res

L6 ADD $testcnt $testcnt 1
   SET $res 0
   ADD $res $res 1
   BGT $res 1 L1
   BLT $res 1 L1

   ADD $testcnt $testcnt 1
   SET $res 1
   SUB $res $res 1
   BGT $res 0 L7
   BLT $res 0 L7

   ADD $testcnt $testcnt 1
   SET $res 2
   MUL $res $res 2
   BGT $res 4 L7
   BLT $res 4 L7


   ADD $testcnt $testcnt 1
   SET $res 4
   DIV $res $res 2
   BGT $res 2 L7
   BLT $res 2 L7

   ADD $testcnt $testcnt 1
   SET $res 3
   MOD $res $res 3
   BGT $res 0 L7
   BLT $res 0 L7

   ADD $testcnt $testcnt 1
   SET $res 1
   SND $argv[0] $res
   RCV $argv[0] $rcv_res  
   BGT $rcv_res 1 L7
   BLT $rcv_res 1 L7

   ADD $testcnt $testcnt 1
   SET $i 0
L8 SET $array[$i] 1
   ADD $i $i 1
   BLT $i 100 L8

   ADD $testcnt $testcnt 1
   SET $i 0
L9 BGT $array[$i] 1 L7
   BLT $array[$i] 1 L7
   ADD $i $i 1
   BLT $i 100 L9
   
   PRN "SUCCESS"
   RET
L7 PRN "FAILURE TEST " $testcnt $res

