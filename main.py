import requests
import base64
import time
from dataclasses import dataclass
from typing import List, Optional
import json
from datetime import datetime, timedelta

class TidbytBitcoinTracker:
    COINDESK_PRICE_URL = "https://api.coindesk.com/v1/bpi/currentprice.json"
    TIDBYT_API_URL = "https://api.tidbyt.com/v0/devices/{}/push"
    
    # Bitcoin icon encoded in base64
    BTC_ICON = """
    iVBORw0KGgoAAAANSUhEUgAAABEAAAARCAYAAAA7bUf6AAAAlklEQVQ4T2NkwAH+H2T/jy7FaP+
    TEZtyDEG4Zi0TTPXXzoDF0A1DMQRsADbN6MZdO4NiENwQbAbERh1lWLzMmgFGo5iFZBDYEFwuwG
    sISCPUIKyGgDRjAyBXYXMNIz5XgDQga8TpLboYgux8DO/AwoUuLiEqTLBFMcmxQ7V0gssgklIsL
    AYozjsoBoE45OZi5DRBSnkCAMLhlPBiQGHlAAAAAElFTkSuQmCC
    """

    def __init__(self, device_id: str, api_key: str):
        """
        Initialize the Bitcoin tracker with Tidbyt credentials
        
        Args:
            device_id (str): Your Tidbyt device ID
            api_key (str): Your Tidbyt API key
        """
        self.device_id = device_id
        self.api_key = api_key
        self.last_price = None
        self.last_update = None
        self.cache_ttl = timedelta(minutes=4)

    def get_bitcoin_price(self) -> Optional[float]:
        """Fetch current Bitcoin price from CoinDesk API with caching."""
        now = datetime.now()
        
        # Return cached price if it's still valid
        if (self.last_price is not None and 
            self.last_update is not None and 
            now - self.last_update < self.cache_ttl):
            print("Using cached price")
            return self.last_price

        try:
            response = requests.get(self.COINDESK_PRICE_URL)
            if response.status_code == 200:
                data = response.json()
                price = data["bpi"]["USD"]["rate_float"]
                self.last_price = price
                self.last_update = now
                print(f"Fetched new price: ${price:,.2f}")
                return price
            else:
                print(f"Failed to fetch Bitcoin price. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching Bitcoin price: {str(e)}")
            return None

    def create_webp(self) -> Optional[bytes]:
        """Create the WebP image data for Tidbyt display."""
        price = self.get_bitcoin_price()
        if price is None:
            return None

        # Create the Starlark render code
        render_code = f"""
load("render.star", "render")
load("encoding/base64.star", "base64")

BTC_ICON = base64.decode(\"""{self.BTC_ICON}\""")

def main():
    return render.Root(
        child = render.Box(
            render.Row(
                expanded=True,
                main_align="space_evenly",
                cross_align="center",
                children = [
                    render.Image(src=BTC_ICON),
                    render.Text("${int(price)}"),
                ],
            ),
        ),
    )
"""
        try:
            # Use pixlet's API endpoint to render the WebP
            response = requests.post(
                "https://pixlet.tidbyt.com/render",
                data=render_code.encode('utf-8')
            )
            
            if response.status_code != 200:
                print(f"Failed to render WebP. Status code: {response.status_code}")
                return None
                
            return response.content
        except Exception as e:
            print(f"Error creating WebP: {str(e)}")
            return None

    def push_to_tidbyt(self) -> bool:
        """Push the current Bitcoin price display to the Tidbyt device."""
        webp_data = self.create_webp()
        if not webp_data:
            return False

        try:
            # Encode the WebP data as base64 for the API
            encoded_webp = base64.b64encode(webp_data).decode('utf-8')
            
            # Prepare the API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "image": encoded_webp,
                "installation_id": "bitcoin-tracker",  # Unique ID for this app installation
                "background": True  # Allow background updates
            }

            # Push to device
            response = requests.post(
                self.TIDBYT_API_URL.format(self.device_id),
                headers=headers,
                json=data
            )

            if response.status_code == 200:
                print("Successfully pushed to Tidbyt!")
                return True
            else:
                print(f"Failed to push to Tidbyt. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"Error pushing to Tidbyt: {str(e)}")
            return False

    def run_continuous_updates(self, update_interval: int = 300):
        """
        Continuously update the Tidbyt display
        
        Args:
            update_interval (int): Seconds between updates (default: 5 minutes)
        """
        print(f"Starting Bitcoin price updates every {update_interval} seconds...")
        try:
            while True:
                success = self.push_to_tidbyt()
                if not success:
                    print("Failed to update. Will retry...")
                time.sleep(update_interval)
        except KeyboardInterrupt:
            print("\nStopping Bitcoin tracker...")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")

def main():
    # Load configuration from file
    try:
        with open('tidbyt_config.json', 'r') as f:
            config = json.load(f)
            device_id = config['device_id']
            api_key = config['api_key']
    except FileNotFoundError:
        print("Please create a tidbyt_config.json file with your device_id and api_key")
        return
    except KeyError:
        print("Config file must contain 'device_id' and 'api_key' fields")
        return

    # Create and run the tracker
    tracker = TidbytBitcoinTracker(device_id, api_key)
    tracker.run_continuous_updates()

if __name__ == "__main__":
    main()