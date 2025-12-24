#!/usr/bin/env bash

# --- Logging: ensure a filename was provided ---
if [[ -z "$1" ]]; then
  echo "ERROR: No input file provided." >&2
  echo "Usage: $0 <meshcore-bot output file>" >&2
   exit 1
fi


input_file="$1"


cmd_output=$(grep -v Direct $input_file | grep EXTRAC | cut -f6- -d- |cut -f2- -d: | cut -f1 -d\( | cut -f2 -d\ | sort -u | awk -F, '{ for (i=NF; i>0; i--) printf "%s%s", $i, (i>1?",":"\n") }')


input_file="$1"
declare -A seen

while IFS=',' read -r -a cols; do
    path=""
    indent=""

    for col in "${cols[@]}"; do
        path="$path/$col"

        if [[ -z "${seen[$path]}" ]]; then
            echo "${indent}${col}"
            seen[$path]=1
        fi

        indent="$indent  "
    done
#done < "$input_file"
done <<< "$cmd_output"
