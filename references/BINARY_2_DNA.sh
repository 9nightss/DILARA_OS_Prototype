#!/bin/bash
#small code to make DNA sequence from binary data in fasta format
echo "
    BINARY_2_DNA.sh - written by Abhijeet Singh (abhijeetsingh.aau@gmail.com)

    Translating BINARY to DNA bases

please provide the name of your binary data file"
read filename
binary_file=filename

awk 'BEGIN{RS=">"}NR>1{sub("\n","\t"); gsub("\n",""); print RS$0}' ${!binary_file} > ${!binary_file}_tab
cat ${!binary_file}_tab | awk '{print $1}' > ${!binary_file}_tab_col1
cat ${!binary_file}_tab | awk '{print $2}' > ${!binary_file}_tab_col2
cat ${!binary_file}_tab_col2 |  sed 's/.\{2\}/& /g' > ${!binary_file}_pairs
echo "
-----------------------------------
The codes used for translation are:
    00=A
        11=T
           01=C
                10=G
-----------------------------------"
sed -i 's/00 /A /g;s/11 /T /g; s/01 /C /g;s/10 /G /g' ${!binary_file}_pairs
sed -i 's/ //g' ${!binary_file}_pairs
paste ${!binary_file}_tab_col1 ${!binary_file}_pairs | column -s $'\n' -t > ${!binary_file}.fasta
sed -i 's/\t/\n/g' ${!binary_file}.fasta
rm -f ${!binary_file}_tab ${!binary_file}_tab_col1 ${!binary_file}_tab_col2 ${!binary_file}_tab_col2_2 ${!binary_file}_pairs
echo "                            ========================="
echo "your result file is ---->>> ${!binary_file}.fasta"
echo "                            ========================="
