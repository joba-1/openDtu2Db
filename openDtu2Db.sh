#!/bin/bash
. ~/.bashrc
conda activate openDtu2Db
exec python -u ~/bin/openDtu2Db.py $@
