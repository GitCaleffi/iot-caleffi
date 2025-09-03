# Make it executable first
chmod +x install_plug_and_play.sh

# Then run with sudo (required for system installation)
sudo ./install_plug_and_play.sh

# Copy files to Raspberry Pi
scp pi_plug_and_play_client.py pi@192.168.1.18:/home/pi/
scp install_plug_and_play.sh pi@192.168.1.18:/home/pi/

# SSH into Pi
ssh pi@192.168.1.18

# Make executable and install
chmod +x install_plug_and_play.sh
sudo ./install_plug_and_play.sh

# Copy files to Raspberry Pi
scp pi_plug_and_play_client.py pi@192.168.1.18:/home/pi/
scp install_plug_and_play.sh pi@192.168.1.18:/home/pi/

# SSH into Pi
ssh pi@192.168.1.18

# Make executable and install
chmod +x install_plug_and_play.sh
sudo ./install_plug_and_play.sh