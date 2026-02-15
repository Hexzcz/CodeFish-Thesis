import ftplib
import os
import gzip
import numpy as np

def find_rain_luzon():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Check Feb 4 and Feb 3 (Today/Yesterday)
    days = [('2026', '02', '03'), ('2026', '02', '04')]
    
    for yr, mo, day in days:
        path = f"/now/half_hour_G/{yr}/{mo}/{day}/"
        try:
            ftp.cwd(path)
            files = sorted([f for f in ftp.nlst() if f.endswith('.gz')])
            for f_name in files[::4]: # Every 2 hours
                local = "luzon.gz"
                with open(local, 'wb') as fo: ftp.retrbinary(f"RETR {f_name}", fo)
                with gzip.open(local, 'rb') as fo:
                    data = np.frombuffer(fo.read(), dtype='<f4').reshape(1200, 3600)
                    def lat_idx(lat): return int((60.0 - lat) / 0.1)
                    def lon_idx(lon): return int(lon / 0.1)
                    
                    # Luzon + surrounding waters
                    l1, l2 = lat_idx(20), lat_idx(10)
                    o1, o2 = lon_idx(118), lon_idx(126)
                    
                    # Search for any non-zero point
                    mask = (data[l1:l2, o1:o2] > 0.5)
                    if np.any(mask):
                        # Find indices of rain
                        coords = np.argwhere(mask)
                        r, c = coords[0]
                        lat = 20 - (r * 0.1)
                        lon = 118 + (c * 0.1)
                        intensity = data[l1+r, o1+c]
                        hour = f_name.split('.')[2][:2]
                        print(f"RAIN FOUND: Date {yr}-{mo}-{day} Hour {hour}:00 UTC at Lat {lat:.1f}, Lon {lon:.1f} (Intensity: {intensity:.2f} mm/h)")
                        ftp.quit()
                        return
                os.remove(local)
        except: continue
    ftp.quit()
    print("No significant rain found in Luzon yet.")

if __name__ == "__main__":
    find_rain_luzon()
