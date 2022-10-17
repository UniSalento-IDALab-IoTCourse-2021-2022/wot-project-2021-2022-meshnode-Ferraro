#! /bin/bash

sudo cp -r /home/pi/project/src/0e020b0a0f070a060d080c0309050401/ /var/lib/bluetooth/mesh/

while true
do
    sudo systemctl stop bluetooth-mesh
    sudo systemctl start bluetooth

    timeout 2 node /home/pi/project/src/index.js  > /home/pi/project/src/scan.txt 

    sudo systemctl stop bluetooth
    sudo systemctl start bluetooth-mesh

    timeout 5 python3 /home/pi/project/src/node.py    

done