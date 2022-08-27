#! /bin/sh
while true
do
    sudo systemctl stop bluetooth-mesh
    sudo systemctl start bluetooth

    timeout 2 node index.js # > scan.txt

    sudo systemctl stop bluetooth
    sudo systemctl start bluetooth-mesh

    timeout 5 python3 node.py    
done