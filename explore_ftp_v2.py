import ftplib

def explore(host, user, password):
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    # Common historical paths
    paths = ['/now/half_hour_G/', '/now/latest/', '/standard/']
    
    for p in paths:
        try:
            print(f"\n--- Exploring {p} ---")
            ftp.cwd(p)
            files = []
            ftp.retrlines('LIST', callback=lambda x: files.append(x))
            for f in files[:10]: # Print first 10
                print(f)
            if len(files) > 10:
                print(f"... and {len(files)-10} more")
        except:
            print(f"Path {p} not found or not accessible.")

    ftp.quit()

if __name__ == "__main__":
    explore("hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404")
