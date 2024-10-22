import os
import json
import spotipy
import time
import threading
from spotipy.oauth2 import SpotifyOAuth
from pythonosc import dispatcher, osc_server, udp_client

config = {}
client = None
sp = None

def create_config():    
    print("No valid configuration file was found. Enter your Spotify App(https://developer.spotify.com/dashboard) details when prompted.")
    client_id = input("Client ID: ")
    client_secret = input("Client Secret: ")
    redirect_uri = input("Redirect URI (default: http://127.0.0.1:9090): ") or "http://127.0.0.1:9090"

    send_port = input(f"Send Port (default: 5006): ") or 5006
    receive_port = input(f"Receive Port (default: 5005): ") or 5005
    ip_address = input("IP Address (default: 127.0.0.1): ") or "127.0.0.1"

    try:
        send_port = int(send_port)
        receive_port = int(receive_port)
    except ValueError:
        print("Ports should be integers. Please try again.")
        return None

    config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "send_port": send_port,
        "receive_port": receive_port,
        "ip_address": ip_address
    }
            
    save_choice = input("Would you like to save the current settings as 'config.json'? (y/n): ")
    if save_choice.lower() == 'y':
        save_configuration(config)
    else:
        print("Configuration not saved.")

    return config

def load_config(filename='config.json'):
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as json_file:
                config = json.load(json_file)
            print(f"Configuration loaded from {filename}")
            return config
        else:
            raise FileNotFoundError
    except (FileNotFoundError, json.JSONDecodeError):
        return

def save_configuration(config, filename='config.json'):
    with open(filename, 'w') as json_file:
        json.dump(config, json_file, indent=4)
    print(f"Configuration saved to {filename}")

def skip_to_next():
    try:
        sp.next_track()
        time.sleep(1)
        client.send_message("/track_name", get_current_track_name())
        client.send_message("/track_image", get_current_track_image())   
        print("Skipped to the next track.")
    except Exception as e:
        print(f"Error skipping to next track: {e}")

def skip_to_previous():
    try:
        sp.previous_track()
        time.sleep(1)
        client.send_message("/track_name", get_current_track_name())
        client.send_message("/track_image", get_current_track_image())
        print("Skipped to the previous track.")
    except Exception as e:
        print(f"Error skipping to previous track: {e}")

def play_pause():
    playback_info = sp.current_playback()
    if playback_info is not None and playback_info['is_playing']:
        sp.pause_playback()
        client.send_message("/is_playing", False)        
        print("Paused the playback.")
    else:
        sp.start_playback()
        client.send_message("/is_playing", True)        
        print("Resumed playback.")

def get_current_track_image(playback):
    playback_info = playback
    if playback_info is not None:
        item = playback_info['item']
        if item and 'album' in item and 'images' in item['album']:
            image_url = item['album']['images'][0]['url'] 
            return image_url
    return ""

def get_current_track_name(playback):
    playback_info = playback
    if playback_info and playback_info['item']:
        return playback_info['item']['name']
    return ""

def get_is_playing(playback):
    playback_info = playback
    if playback_info and playback_info['is_playing']:
        return playback_info['is_playing']
    return False

def update_data():
    while True:
        playback = sp.current_user_playing_track()
        client.send_message("/track_name", get_current_track_name(playback))
        client.send_message("/track_image", get_current_track_image(playback))
        client.send_message("/is_playing", get_is_playing(playback))

        time.sleep(1)

def print_message(address, *args):
    print(f"Received OSC message at {address} with arguments: {args}")

def osc_command_handler(unused_addr, command):
    if command is None:
        print("Received a None command. Ignoring.")
        return

    command = command.lower() 

    match command:
        case 'play_pause':
            play_pause()
        case 'next':
            skip_to_next()
        case 'previous':
            skip_to_previous()
        case 'track_image':
            get_current_track_image()
        case _:
            print(f"Unknown command: {command}")

def setup_osc_dispatcher():
    disp = dispatcher.Dispatcher()
    disp.map("/spotify_control", osc_command_handler)
    disp.set_default_handler(print_message)

    update_thread = threading.Thread(target=update_data)
    update_thread.daemon = True
    update_thread.start()

    return disp

if __name__ == "__main__":
    config = load_config()
    
    if not config:
        config = create_config()

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        redirect_uri=config['redirect_uri'],
        scope="user-library-read user-modify-playback-state user-read-playback-state"
    ))

    client = udp_client.SimpleUDPClient(config['ip_address'], config['send_port'])
    disp = setup_osc_dispatcher()
    server = osc_server.ThreadingOSCUDPServer((config['ip_address'], config['receive_port']), disp)
    print(f"Running at {config['ip_address']}:{config['send_port']}/{config['receive_port']}")
    server.serve_forever()