import ftplib
import os
import gzip
import numpy as np

def scan_for_rain(host, user, password, year, month):
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    base_path = f"/now/half_hour_G/{year}/{month}/"
    print(f"Scanning {base_path} for any rain in Philippines...")
    
    try:
        ftp.cwd(base_path)
        days = sorted(ftp.nlst(), reverse=True)
        
        for day in days[:5]: # Check last 5 days
            day_path = f"{base_path}{day}/"
            ftp.cwd(day_path)
            files = [f for f in ftp.nlst() if f.endswith('.gz')]
            
            if files:
                # Check 1 sample file from this day (e.g., the noon one)
                sample = files[len(files)//2]
                print(f"Checking {day_path}{sample}...")
                
                local_tmp = "tmp_scan.dat.gz"
                with open(local_tmp, 'wb') as f:
                    ftp.retrbinary(f"RETR {sample}", f.write)
                
                with gzip.open(local_tmp, 'rb') as f:
                    data = np.frombuffer(f.read(), dtype='<f4').reshape(1200, 3600)
                    
                    # Philippines Bounding Box (Roughly)
                    # Lat 5 to 20, Lon 115 to 130
                    def lat_to_idx(lat): return int((60.0 - lat) / 0.1)
                    def lon_to_idx(lon): return int(lon / 0.1)
                    
                    l1, l2 = lat_to_idx(20), lat_to_idx(5)
                    o1, o2 = lon_to_idx(115), lon_to_idx(130)
                    
                    ph_data = data[l1:l2, o1:o2]
                    max_rain = np.max(ph_data)
                    
                    if max_rain > 0.5:
                        print(f"FOUND RAIN! Date: {year}-{month}-{day}, Max: {max_rain} mm/h")
                        ftp.quit()
                        os.remove(local_tmp)
                        return f"{year}-{month}-{day}"
                
                os.remove(local_tmp)
            ftp.cwd('..')
            
    except Exception as e:
        print(f"Error: {e}")
    
    ftp.quit()
    return None

if __name__ == "__main__":
    # Check early Feb 2026
    res = scan_for_rain("hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404", "2026", "02")
    if not res:
        # If nothing in Feb, check late Jan 2026
        res = scan_for_rain("hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404", "2026", "01")
