#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


fullcmd="$(realpath $0)" 
thispath="$(dirname $fullcmd)"

source ./gcv/bin/activate

while getopts ":c:m:r:s:t:z:" o ; do
    case "${o}" in 
        c)
            class_name=${OPTARG}
            ;;
        m)
            model_name=${OPTARG}
            ;;
        n)
            num_outputs=${OPTARG}
            ;;
        o)
            output=${OPTARG}
            ;;
        r)
            frame_rate=${OPTARG}
            ;;
        s)
            source_file=${OPTARG}
            ;;
        t)
            topic_name=${OPTARG}
            ;;
        z)
            threshold=${OPTARG}
            ;;
    esac
done


python3 $thispath/infer.py -c $class_name -m $model_name -r $frame_rate \
    -s $source_file -t $topic_name -z $threshold \
    -o $output -n $num_outputs
