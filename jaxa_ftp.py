import ftplib
import os
import gzip
import numpy as np
import json

def fetch_jaxa_forecast(host, user, password, local_path="cache/jaxa/", date="", hour=""):
    """
    Connects to JAXA FTP server and downloads the latest or historical rainfall forecast data.
    """
    print(f"Connecting to JAXA FTP: {host} as {user}... (History: {date} {hour})")
    
    if not os.path.exists(local_path):
        os.makedirs(local_path)
        
    try:
        ftp = ftplib.FTP(host)
        ftp.login(user, password)
        
        # Decide directory based on whether a specific date is requested
        if date:
            # Format date: YYYY-MM-DD -> YYYY/MM/DD
            parts = date.split('-')
            if len(parts) == 3:
                year, month, day = parts
                target_dir = f"/now/half_hour_G/{year}/{month}/{day}/"
                print(f"Navigating to historical directory: {target_dir}")
                ftp.cwd(target_dir)
            else:
                print("Invalid date format. Using latest.")
                ftp.cwd('/now/latest/')
        else:
            ftp.cwd('/now/latest/') 
        
        files = ftp.nlst()
        # Look for the gauge-adjusted real-time data
        target_files = [f for f in files if f.startswith('gsmap_gauge_now') and f.endswith('.gz')]
        
        if not target_files:
            print(f"No files found in {ftp.pwd()}")
            return False
            
        # If a specific hour is requested, find the closest file
        if date and hour:
            # File format: gsmap_gauge_now.YYYYMMDD.HHMM.dat.gz
            target_files = [f for f in target_files if f.split('.')[2].startswith(hour)]
            if not target_files:
                print(f"No files found for hour {hour}. Available files: {files[:5]}...")
                return False

        latest_file = sorted(target_files)[-1]
        local_file_path = os.path.join(local_path, latest_file)
        
        print(f"Downloading: {latest_file}")
        with open(local_file_path, 'wb') as f:
            ftp.retrbinary(f"RETR {latest_file}", f.write)
            
        ftp.quit()
        print("Download complete.")
        
        # Process the downloaded file for QC
        return parse_jaxa_binary_for_qc(local_file_path)
        
    except Exception as e:
        print(f"FTP Error: {e}")
        return False

def parse_jaxa_binary_for_qc(file_path):
    """
    Parses JAXA GSMaP binary data (0.1 degree grid) and extracts Quezon City area.
    Data format: 4-byte float, 3600 (lon) x 1200 (lat)
    Coverage: 60N to 60S
    """
    print(f"Parsing JAXA binary: {file_path}")
    
    try:
        with gzip.open(file_path, 'rb') as f:
            # Map the binary data to a numpy array (3600x1200)
            # JAXA GSMaP binary is often 4-byte floats in Little Endian
            data = np.frombuffer(f.read(), dtype='<f4').reshape(1200, 3600)
            
            # Flip since 0 is 60N
            # Lat range: 60N to 60S (0.1 degree steps) -> 1200 points
            # Lon range: 0 to 360E (0.1 degree steps) -> 3600 points
            
            # Wider Bounding Box for better context: 
            # Lat 14.0 to 15.0, Lon 120.5 to 121.5
            def lat_to_idx(lat): return int((60.0 - lat) / 0.1)
            def lon_to_idx(lon): return int(lon / 0.1)
            
            lat_start, lat_end = lat_to_idx(15.0), lat_to_idx(14.0)
            lon_start, lon_end = lon_to_idx(120.5), lon_to_idx(121.5)
            
            # Extract the region
            qc_data = data[lat_start:lat_end+1, lon_start:lon_end+1]
            
            print(f"Extracted Grid Shape: {qc_data.shape}")
            
            # Create a GeoJSON-like grid for the frontend
            features = []
            for r in range(qc_data.shape[0]):
                for c in range(qc_data.shape[1]):
                    val = float(qc_data[r, c])
                    
                    # Handle JAXA "No Data" or invalid values (usually negative)
                    if val < 0 or val > 500:
                        val = 0.0
                    
                    # Coordinate mid-points for the 0.1 degree cell
                    # r=0 is lat_start (highest lat), so we move DOWN
                    lat = 60.0 - (lat_start + r) * 0.1
                    # c=0 is lon_start (lowest lon), so we move RIGHT
                    lon = (lon_start + c) * 0.1
                    
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [lon, lat],
                                [lon + 0.1, lat],
                                [lon + 0.1, lat - 0.1],
                                [lon, lat - 0.1],
                                [lon, lat]
                            ]]
                        },
                        "properties": {
                            "intensity": val,
                            "source": "JAXA Real-time"
                        }
                    })
            
            # Extract the actual data timestamp from the filename
            # Format: gsmap_gauge_now.YYYYMMDD.HHMM.dat.gz
            fname = os.path.basename(file_path)
            data_date = "Unknown"
            if len(fname.split('.')) >= 3:
                ts_part = fname.split('.')[1] # YYYYMMDD
                hr_part = fname.split('.')[2] # HHMM
                data_date = f"{ts_part[:4]}-{ts_part[4:6]}-{ts_part[6:8]} {hr_part[:2]}:{hr_part[2:4]} UTC"

            # Save the processed data for the web app
            output = {
                "type": "FeatureCollection",
                "features": features,
                "timestamp": data_date,
                "processed_at": datetime.datetime.now().isoformat(),
                "filename": fname
            }
            
            with open("cache/jaxa_qc_latest.json", "w") as out:
                json.dump(output, out)
            
            print("Successfully extracted QC rainfall data.")
            return True

    except Exception as e:
        print(f"Parsing Error: {e}")
        return False

import datetime
if __name__ == "__main__":
    fetch_jaxa_forecast("hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404")
