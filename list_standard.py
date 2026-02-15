import ftplib

def list_standard():
    host, user, password = "hokusai.eorc.jaxa.jp", "rainmap", "Niskur+1404"
    ftp = ftplib.FTP(host)
    ftp.login(user, password)
    
    try:
        print("\n--- Exploring /standard/ ---")
        ftp.cwd('/standard/')
        ftp.retrlines('LIST')
        
        # Check v9 or v8
        subdirs = ftp.nlst()
        if 'v9' in subdirs:
            print("\n--- Exploring /standard/v9/ ---")
            ftp.cwd('v9')
            ftp.retrlines('LIST')
            
            p = 'hourly'
            if p in ftp.nlst():
                print(f"\n--- Exploring /standard/v9/{p}/ ---")
                ftp.cwd(p)
                ftp.retrlines('LIST')
    except Exception as e:
        print(f"Error: {e}")
    ftp.quit()

if __name__ == "__main__":
    list_standard()
