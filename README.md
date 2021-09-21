# A Raspberry Pi, E-ink powered dashboard for nicehash stats

This project is a simple personal project leveraging a Raspberry Pi Zero W, with an e-ink hat by Waveshare.  All example code from Waveshare is included.

Reference their wiki for prerequisites here https://www.waveshare.com/wiki/2.13inch_e-Paper_HAT

## Lot of changes from me
* change to waveshare 2.7 paper display
* add proxy for mining rigs to open port 500 and publish all values from localhost:4000
* display real hasrate from miner
* dispay money in euro
* send alarm email if hasrate strong changed

## Usage

Inside the run directory you'll find the guts of the script, nhdash.py.  The script handles authentication and a few calls to NiceHash API (https://www.nicehash.com/docs/rest). Modify to suit your needs.

execute run/nhdash.py as sudo (ie: sudo python3 nhdash.py), and the script will run continuously, updating the e-ink display every 5 minutes.  Add it to your rc.local to execute on boot (or however you'd like)

**Credentials**

Copy lib/nicehash_creds/api_info_sample.py to api_info.py and enter your credentials in that file.
