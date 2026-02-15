import ftplib
import os
import gzip
import numpy as np

def find_rain():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # We will check Feb 4 first (today/yesterday depending on UTC)
    # Then walk backwards
    years = ['2026']
    months = ['02', '01']
    
    for yr in years:
        for mo in months:
            try:
                path = f"/now/half_hour_G/{yr}/{mo}/"
                ftp.cwd(path)
                days = sorted(ftp.nlst(), reverse=True)
                for day in days[:10]: # Look back 10 days
                    ftp.cwd(day)
                    files = [f for f in ftp.nlst() if f.endswith('.gz')]
                    if files:
                        file_to_check = files[len(files)//2] # Middle of the day
                        print(f"Checking: {yr}-{mo}-{day} {file_to_check}")
                        
                        local = f"check.gz"
                        with open(local, 'wb') as f:
                            ftp.retrbinary(f"RETR {file_to_check}", f.write)
                        
                        with gzip.open(local, 'rb') as f:
                            data = np.frombuffer(f.read(), dtype='<f4').reshape(1200, 3600)
                            # Philippines bounding Box
                            def lat_to_idx(lat): return int((60.0 - lat) / 0.1)
                            def lon_to_idx(lon): return int(lon / 0.1)
                            
                            # Wide PH search
                            l1, l2 = lat_to_idx(19), lat_to_idx(4)
                            o1, o2 = lon_to_idx(116), lon_to_idx(127)
                            ph_max = np.max(data[l1:l2, o1:o2])
                            
                            if ph_max > 1.0:
                                print(f"--- SUCCESS: {yr}-{mo}-{day} has rain ({ph_max} mm/h) ---")
                                ftp.quit()
                                return
                        os.remove(local)
                    ftp.cwd("..")
            except:
                continue
    ftp.quit()

if __name__ == "__main__":
    find_rain()
