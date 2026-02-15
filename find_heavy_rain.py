import ftplib
import os
import gzip
import numpy as np

def find_heavy_rain():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Check Nov 15-20 (Typhoon Pepito/Ofel period)
    base = "/now/half_hour_G/2024/11/"
    days = ['15', '16', '17', '18', '19', '20']
    
    def lat_idx(lat): return int((60.0 - lat) / 0.1)
    def lon_idx(lon): return int(lon / 0.1)
    r1, r2 = lat_idx(14.8), lat_idx(14.6)
    c1, c2 = lon_idx(121.0), lon_idx(121.2)

    for d in days:
        try:
            ftp.cwd(f"{base}{d}/")
            files = sorted([f for f in ftp.nlst() if f.endswith('.gz')])
            for f_name in files[::2]: # Check every hour
                local = "heavy.gz"
                with open(local, "wb") as fo: ftp.retrbinary(f"RETR {f_name}", fo.write)
                with gzip.open(local, "rb") as fo:
                    data = np.frombuffer(fo.read(), dtype='<f4').reshape(1200, 3600)
                    val = np.max(data[r1:r2, c1:c2])
                    if val > 1.0:
                        hour = f_name.split('.')[2][:2]
                        print(f"!!! HEAVY RAIN FOUND !!! Date: 2024-11-{d} Hour: {hour}:00 UTC -> QC Rain: {val:.2f} mm/h")
                        ftp.quit()
                        return
                os.remove(local)
        except: continue
    
    ftp.quit()

if __name__ == "__main__":
    find_heavy_rain()
