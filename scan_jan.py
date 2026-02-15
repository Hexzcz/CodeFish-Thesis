import ftplib
import os
import gzip
import numpy as np

def scan_january():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Quezon City Bounding Box
    def lat_to_idx(lat): return int((60.0 - lat) / 0.1)
    def lon_to_idx(lon): return int(lon / 0.1)
    l1, l2 = lat_to_idx(14.8), lat_to_idx(14.6)
    o1, o2 = lon_to_idx(121.0), lon_to_idx(121.2)

    # Check Jan 10-20 (Mid Jan)
    days = [str(i).zfill(2) for i in range(1, 32)]
    for day in reversed(days):
        path = f"/now/half_hour_G/2026/01/{day}/"
        try:
            ftp.cwd(path)
            files = sorted([f for f in ftp.nlst() if f.endswith('.gz')])
            if not files: continue
            
            # Check 3 times per day (Morning, Noon, Night)
            indices = [0, len(files)//2, len(files)-1]
            for idx in indices:
                f_name = files[idx]
                local = "tmp_jan.gz"
                with open(local, 'wb') as fo:
                    ftp.retrbinary(f"RETR {f_name}", fo)
                
                with gzip.open(local, 'rb') as fo:
                    data = np.frombuffer(fo.read(), dtype='<f4').reshape(1200, 3600)
                    qc_max = np.max(data[l1:l2, o1:o2])
                    if qc_max > 0.5:
                        hour = f_name.split('.')[2][:2]
                        print(f"!!! FOUND QC RAIN !!! Date: 2026-01-{day} Hour: {hour}:00 UTC, Intensity: {qc_max} mm/h")
                        ftp.quit()
                        return
                os.remove(local)
            ftp.cwd("/..")
        except:
            continue
    ftp.quit()

if __name__ == "__main__":
    scan_january()
