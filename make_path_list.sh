#!/usr/bin/env bash


declare -A seen

# --- Logging: ensure a filename was provided ---
if [[ -z "$1" ]]; then
  echo "ERROR: No input file provided." >&2
  echo "Usage: $0 <meshcore-bot output file>" >&2
   exit 1
fi


input_file="$1"


cmd_output=$(grep -v Direct $input_file | grep EXTRAC | cut -f6- -d- |cut -f2- -d: | cut -f1 -d\( | cut -f2 -d\ | sort -u | awk -F, '{ for (i=NF; i>0; i--) printf "%s%s", $i, (i>1?",":"\n") }')


while IFS=',' read -r -a nodes; do
    for ((i=0; i<${#nodes[@]}-1; i++)); do
        echo "${nodes[i]}-${nodes[i+1]}"
    done
done <<< "$cmd_output"
