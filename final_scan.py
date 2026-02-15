import ftplib
import os
import gzip
import numpy as np

def final_scan():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Quezon City Bounding Box
    def lat_idx(lat): return int((60.0 - lat) / 0.1)
    def lon_idx(lon): return int(lon / 0.1)
    r1, r2 = lat_idx(14.8), lat_idx(14.6)
    c1, c2 = lon_idx(121.0), lon_idx(121.2)

    # Scouring November 2024 - a very wet month
    base = "/now/half_hour_G/2024/11/"
    ftp.cwd(base)
    days = sorted(ftp.nlst(), reverse=True)
    
    for d in days:
        try:
            ftp.cwd(f"{base}{d}/")
            files = [f for f in ftp.nlst() if f.endswith('.gz')]
            # Check just 2 files from each day to speed up
            for f_name in [files[0], files[len(files)//2]]:
                local = "t.gz"
                try:
                    with open(local, "wb") as fo: ftp.retrbinary(f"RETR {f_name}", fo.write)
                    with gzip.open(local, "rb") as fo:
                        data = np.frombuffer(fo.read(), dtype='<f4').reshape(1200, 3600)
                        val = np.max(data[r1:r2, c1:c2])
                        if val > 0.3:
                            hour = f_name.split('.')[2][:2]
                            print(f"MATCH: 2024-11-{d} {hour}:00 UTC -> QC Rain: {val:.2f} mm/h")
                            ftp.quit()
                            return
                finally:
                    if os.path.exists(local): os.remove(local)
            ftp.cwd("..")
        except: continue
    
    ftp.quit()

if __name__ == "__main__":
    final_scan()
