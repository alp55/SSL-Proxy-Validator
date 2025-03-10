from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pynput import keyboard
import sys
import socks
import socket
from urllib3.contrib.socks import SOCKSProxyManager
import urllib3
import warnings

# SSL uyarılarını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

class ProxyTester:
    def __init__(self):
        self.test_url = "https://www.google.com"  # SSL kullanan test URL'si
        self.connect_timeout = 5  # Bağlantı timeout süresini düşür
        self.read_timeout = 5  # Okuma timeout süresini düşür
        self.max_workers = 20  # Aynı anda test edilecek proxy sayısını artır
        self.max_working_proxies = 100  # Maksimum çalışan proxy sayısı
        self.max_retry = 3  # Yeniden deneme sayısı
        self.max_timeout = 1500  # Maksimum kabul edilebilir timeout (ms)
        
        self.original_socket = socket.socket  # Orijinal socket'i sakla
        self.max_proxy_attempts = 50  # Her proxy için maksimum deneme sayısı
        self.part_number = None  # Terminal parça numarası
        
        # Blacklist için yeni değişkenler
        self.blacklisted_ips = {
            "98.8.195.160",
            "189.125.109.66"
        }  # Bilinen problemli IP'ler
        
        # İstatistikler
        self.total_tested = 0
        self.ssl_success = 0
        self.ssl_failed = 0
        self.timeout_failed = 0
        self.connection_failed = 0
        self.should_stop = False
        self.working_proxies = []
        self.proxy_url: str | None = None  # URL tipi tanımlaması
        self.tested_proxies = set()  # Test edilen proxy'leri takip etmek için
        self.proxy_attempts = {}  # Her proxy için deneme sayısını takip etmek için
        
        # Klavye dinleyicisini başlat
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.keyboard_listener.start()
        
        self.urls_file = "proxy_urls.json"  # JSON dosya yolu
        
    def save_url(self, url):
        """URL'yi JSON dosyasına kaydeder."""
        try:
            urls = []
            if os.path.exists(self.urls_file):
                with open(self.urls_file, 'r', encoding='utf-8') as f:
                    urls = json.load(f)
                    
            if url not in urls:
                urls.append(url)
                
            with open(self.urls_file, 'w', encoding='utf-8') as f:
                json.dump(urls, f, indent=4)
            print(f"\nURL başarıyla kaydedildi: {url}")
            
        except Exception as e:
            print(f"URL kaydetme hatası: {str(e)}")

    def load_saved_urls(self):
        """Kaydedilmiş URL'leri yükler."""
        try:
            if os.path.exists(self.urls_file):
                with open(self.urls_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"URL'leri yükleme hatası: {str(e)}")
            return []
        
    def on_press(self, key):
        """Klavye tuşu basıldığında."""
        try:
            if key.char == 's':
                print("\n's' tuşuna basıldı. Program durduruluyor...")
                self.should_stop = True
                # Çalışan proxy'leri kaydet ve programı sonlandır
                if hasattr(self, 'working_proxies') and self.working_proxies:
                    print("\nÇalışan proxy'ler kaydediliyor...")
                    
                    # Her terminal kendi parça numarasına göre ayrı dosyaya kaydetsin
                    if hasattr(self, 'part_number'):
                        output_file = f'ssl_working_proxies_part_{self.part_number}.csv'
                        with open(output_file, 'w', encoding='utf-8', newline='') as f:
                            f.write("ip,port,protocol,timeout\n")
                            for proxy in sorted(self.working_proxies, key=lambda x: float(x['timeout'])):
                                f.write(f"{proxy['ip']},{proxy['port']},{proxy['protocol']},{proxy['timeout']}\n")
                        print(f"\nProxy'ler {output_file} dosyasına kaydedildi!")
                
                print("\nProgram sonlandırılıyor...")
                os._exit(0)
        except AttributeError:
            pass
            
    def print_stats(self):
        """Test istatistiklerini yazdırır."""
        sys.stdout.write("\033[K")  # Satırı temizle
        success_rate = round((self.ssl_success / self.total_tested * 100), 2) if self.total_tested > 0 else 0
        print(
            f"\rTest edilen: {self.total_tested} | "
            f"Başarılı: {self.ssl_success} ({success_rate}%) | "
            f"Başarısız: {self.ssl_failed} | "
            f"Timeout: {self.timeout_failed} | "
            f"Bağlantı Hatası: {self.connection_failed} | "
            f"Devam ediyor...", 
            end='', 
            flush=True
        )
        
    def test_proxy(self, proxy):
        """Tek bir proxy'i test eder."""
        # Proxy string'i bir kez oluştur
        proxy_str = f"{proxy['ip']}:{proxy['port']}"
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        
        # IP blacklist'te mi kontrol et
        if proxy['ip'] in self.blacklisted_ips:
            print(f"\nProxy blacklist'te: {proxy_str}")
            return None
        
        # Bu proxy daha önce test edildi mi?
        if proxy_str in self.tested_proxies:
            print(f"\nProxy zaten test edilmiş: {proxy_str}")
            return None
            
        # Proxy'yi test edildi olarak işaretle
        self.tested_proxies.add(proxy_str)
        retry_count = 0
        
        while retry_count < self.max_retry and not self.should_stop:
            if retry_count == 0:
                print(f"\nProxy test ediliyor: {proxy_url}")
            else:
                print(f"Yeniden deneniyor ({retry_count + 1}/{self.max_retry}): {proxy_url}")
            
            try:
                session = requests.Session()
                session.trust_env = False
                session.verify = False
                
                proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                
                head_response = session.head(
                    self.test_url,
                    proxies=proxies,
                    timeout=(self.connect_timeout, self.read_timeout),
                    verify=True,
                    allow_redirects=True
                )
                
                if head_response.status_code == 200:
                    start_time = time.time()
                    response = session.get(
                        self.test_url,
                        proxies=proxies,
                        timeout=(self.connect_timeout, self.read_timeout),
                        verify=False,
                        allow_redirects=True
                    )
                    
                    end_time = time.time()
                    timeout = round((end_time - start_time) * 1000, 2)
                    
                    if timeout > self.max_timeout:
                        self.timeout_failed += 1
                        print(f"Proxy çok yavaş: {proxy_url} (Timeout: {timeout}ms)")
                        break  # Yavaş proxy'yi direkt reddet
                    
                    if response.status_code == 200:
                        proxy['timeout'] = timeout
                        proxy['protocol'] = 'http'
                        self.ssl_success += 1
                        print(f"Proxy çalışıyor: {proxy_url} (Timeout: {timeout}ms)")
                        self.total_tested += 1
                        self.print_stats()
                        return proxy
                        
            except (requests.exceptions.ConnectTimeout, ConnectionRefusedError):
                self.connection_failed += 1
                print(f"Bağlantı reddedildi: {proxy_url}")
                break  # Bağlantı reddedildiyse direkt reddet
            except requests.exceptions.ReadTimeout:
                self.timeout_failed += 1
                print(f"Okuma zaman aşımı: {proxy_url}")
                break  # Timeout olduysa direkt reddet
            except requests.exceptions.ProxyError:
                print(f"Proxy hatası: {proxy_url}")
                break  # Proxy hatası varsa direkt reddet
            except Exception as e:
                print(f"Bağlantı hatası: {proxy_url} - {str(e)}")
                retry_count += 1
                continue
                
        # Tüm denemeler başarısız oldu
        self.ssl_failed += 1
        print(f"Proxy erişilebilir değil: {proxy_str}")
        
        self.total_tested += 1
        self.print_stats()
        return None

    def test_with_selenium(self, proxy):
        """Proxy'i Selenium ile test eder."""
        driver = None
        proxy_str = None
        try:
            options = Options()
            proxy_str = f"http://{proxy['ip']}:{proxy['port']}"
            options.add_argument(f'--proxy-server={proxy_str}')
            options.add_argument('--headless')  # Görünmez modda çalış
            
            service = Service(executable_path="chromedriver.exe")
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(self.connect_timeout)  # connect_timeout kullan
            
            start_time = time.time()
            driver.get(self.test_url)
            end_time = time.time()
            
            timeout = round((end_time - start_time) * 1000, 2)
            proxy['timeout'] = timeout
            print(f"Selenium Test Başarılı: {proxy_str} (Timeout: {timeout}ms)")
            
            if driver:
                driver.quit()
            return proxy
            
        except Exception as e:
            if proxy_str:
                print(f"Selenium Test Hatası: {proxy_str} - {str(e)}")
            if driver:
                driver.quit()
            return None
            
    def load_proxies(self, url=None):
        """IP:PORT formatındaki proxy listesini yükler."""
        proxies = []
        
        try:
            if url:
                print(f"\nProxy listesi URL'den yükleniyor: {url}")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    proxy_list = response.text.split('\n')
                else:
                    print(f"URL'den proxy listesi çekilemedi! Durum kodu: {response.status_code}")
                    return []
            else:
                print("\nProxy listesi dosyadan yükleniyor...")
                with open('test_proxy.txt', 'r', encoding='utf-8') as f:
                    proxy_list = f.readlines()
            
            for line in proxy_list:
                line = line.strip()
                if line:
                    try:
                        ip, port = line.split(':')
                        proxies.append({
                            'ip': ip,
                            'port': port,
                            'protocol': 'http'  # Varsayılan olarak http
                        })
                    except:
                        continue
                        
            print(f"\n{len(proxies)} proxy yüklendi.")
            return proxies
            
        except requests.exceptions.RequestException as e:
            print(f"URL'den proxy listesi çekilirken hata oluştu: {str(e)}")
            return []
        except Exception as e:
            print(f"Proxy yükleme hatası: {str(e)}")
            return []

    def save_working_proxies(self, working_proxies):
        """Çalışan proxy'leri CSV dosyasına kaydeder."""
        try:
            # Önce mevcut çalışan proxy'leri oku
            existing_proxies = []
            if os.path.exists('ssl_working_proxies.csv'):
                with open('ssl_working_proxies.csv', 'r', encoding='utf-8') as f:
                    next(f)  # Başlık satırını atla
                    for line in f:
                        try:
                            ip, port, protocol, timeout = line.strip().split(',')
                            existing_proxies.append({
                                'ip': ip,
                                'port': port,
                                'protocol': protocol,
                                'timeout': float(timeout)
                            })
                        except ValueError:
                            continue
            
            # Yeni proxy'leri ekle
            all_proxies = existing_proxies + working_proxies
            
            # Tekrar eden proxy'leri temizle (ip:port kombinasyonuna göre)
            unique_proxies = {}
            for proxy in all_proxies:
                proxy_key = f"{proxy['ip']}:{proxy['port']}"
                if proxy_key not in unique_proxies or float(proxy['timeout']) < float(unique_proxies[proxy_key]['timeout']):
                    unique_proxies[proxy_key] = proxy
            
            # Timeout'a göre sırala
            sorted_proxies = sorted(unique_proxies.values(), key=lambda x: float(x['timeout']))
            
            # CSV olarak kaydet
            with open('ssl_working_proxies.csv', 'w', encoding='utf-8', newline='') as f:
                f.write("ip,port,protocol,timeout\n")
                for proxy in sorted_proxies:
                    f.write(f"{proxy['ip']},{proxy['port']},{proxy['protocol']},{proxy['timeout']}\n")
                    
            print(f"\nToplam {len(sorted_proxies)} proxy kaydedildi!")
            if sorted_proxies:
                print("\nEn hızlı 3 proxy:")
                for i, proxy in enumerate(sorted_proxies[:3], 1):
                    print(f"{i}. {proxy['protocol'].upper()}: {proxy['ip']}:{proxy['port']} ({proxy['timeout']}ms)")
                    
        except Exception as e:
            print(f"\nProxy kaydetme hatası: {str(e)}")
        
    def run(self):
        """Tüm proxy'leri test eder."""
        proxies = self.load_proxies(url=getattr(self, 'proxy_url', None))
        if not proxies:
            print("Test edilecek proxy bulunamadı!")
            return
        
        print(f"\n{len(proxies)} proxy test edilecek...")
        print("Durdurmak için 's' tuşuna basın...")
        self.working_proxies = []  # Listeyi temizle
        
        # Önce requests ile test et
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for proxy in proxies:
                if self.should_stop:
                    print("\nTest durduruluyor...")
                    break
                    
                if len(self.working_proxies) >= self.max_working_proxies:
                    print(f"\n{self.max_working_proxies} çalışan proxy bulundu!")
                    break
                    
                futures.append(executor.submit(self.test_proxy, proxy))
            
            for future in as_completed(futures):
                if self.should_stop:
                    print("\nTest durduruluyor...")
                    executor.shutdown(wait=False)
                    break
                    
                result = future.result()
                if result:
                    self.working_proxies.append(result)
                    if len(self.working_proxies) >= self.max_working_proxies:
                        print(f"\n{self.max_working_proxies} çalışan proxy bulundu!")
                        break
        
        if not self.should_stop:
            print("\n\nTest sonuçları:")
            print(f"Toplam test edilen: {self.total_tested}")
            print(f"SSL Başarılı: {self.ssl_success}")
            print(f"SSL Başarısız: {self.ssl_failed}")
            print(f"Timeout Hatası: {self.timeout_failed}")
            print(f"Bağlantı Hatası: {self.connection_failed}")
            print(f"Çalışan proxy: {len(self.working_proxies)}")
            
            # Timeout'a göre sırala
            self.working_proxies.sort(key=lambda x: x['timeout'])
            
            # Sonuçları kaydet
            self.save_working_proxies(self.working_proxies)
        
        # Klavye dinleyicisini durdur
        self.keyboard_listener.stop()

    def load_proxies_from_csv(self):
        """CSV dosyasından proxy'leri yükler."""
        proxies = []
        
        if not os.path.exists('ssl_working_proxies.csv'):
            print("\nssl_working_proxies.csv dosyası bulunamadı!")
            return []
            
        try:
            print("\nProxy'ler CSV dosyasından yükleniyor...")
            with open('ssl_working_proxies.csv', 'r', encoding='utf-8') as f:
                # Başlık satırını atla
                next(f)
                # Satırları oku
                for line in f:
                    try:
                        ip, port, protocol, timeout = line.strip().split(',')
                        proxies.append({
                            'ip': ip,
                            'port': port,
                            'protocol': protocol,
                            'timeout': float(timeout)
                        })
                    except ValueError:
                        continue
            
            print(f"\n{len(proxies)} proxy yüklendi.")
            return proxies
            
        except Exception as e:
            print(f"CSV dosyası okuma hatası: {str(e)}")
            return []

    def test_csv_proxies(self):
        """CSV dosyasındaki proxy'leri test eder ve çalışmayanları temizler."""
        proxies = self.load_proxies_from_csv()
        if not proxies:
            print("Test edilecek proxy bulunamadı!")
            return
        
        print(f"\n{len(proxies)} proxy test edilecek...")
        print("Durdurmak için 's' tuşuna basın...")
        self.working_proxies = []  # Listeyi temizle
        
        # Proxy'leri test et
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Aktif future'ları takip etmek için set kullan
            active_futures = set()
            tested_proxies = set()  # Test edilen proxy'leri takip et
            
            for proxy in proxies:
                if self.should_stop:
                    print("\nTest durduruluyor...")
                    break
                    
                if len(self.working_proxies) >= self.max_working_proxies:
                    print(f"\n{self.max_working_proxies} çalışan proxy bulundu!")
                    break
                    
                # Proxy daha önce test edildi mi kontrol et
                proxy_str = f"{proxy['ip']}:{proxy['port']}"
                if proxy_str in tested_proxies:
                    print(f"\nProxy zaten test edilmiş: {proxy_str}")
                    continue
                    
                tested_proxies.add(proxy_str)  # Test edilecek proxy'yi kaydet
                future = executor.submit(self.test_proxy, proxy)
                active_futures.add(future)
                
                # Tamamlanan future'ları kontrol et ve sonuçları işle
                completed = {f for f in active_futures if f.done()}
                for future in completed:
                    active_futures.remove(future)
                    result = future.result()
                    if result:
                        self.working_proxies.append(result)
                
                # CPU kullanımını azaltmak için kısa bir bekleme
                time.sleep(0.1)
            
            # Kalan aktif future'ları bekle
            for future in as_completed(active_futures):
                if self.should_stop:
                    break
                result = future.result()
                if result:
                    self.working_proxies.append(result)
        
        if not self.should_stop:
            print("\n\nTest sonuçları:")
            print(f"Toplam test edilen: {self.total_tested}")
            print(f"SSL Başarılı: {self.ssl_success}")
            print(f"SSL Başarısız: {self.ssl_failed}")
            print(f"Timeout Hatası: {self.timeout_failed}")
            print(f"Bağlantı Hatası: {self.connection_failed}")
            print(f"Çalışan proxy: {len(self.working_proxies)}")
            
            # Timeout'a göre sırala
            self.working_proxies.sort(key=lambda x: x['timeout'])
            
            # Yeni CSV dosyası oluştur
            with open('ssl_working_proxies.csv', 'w', encoding='utf-8', newline='') as f:
                f.write("ip,port,protocol,timeout\n")
                for proxy in self.working_proxies:
                    f.write(f"{proxy['ip']},{proxy['port']},{proxy['protocol']},{proxy['timeout']}\n")
                    
            print(f"\nÇalışan {len(self.working_proxies)} proxy kaydedildi!")
            if self.working_proxies:
                print(f"En hızlı proxy: {self.working_proxies[0]['ip']}:{self.working_proxies[0]['port']} ({self.working_proxies[0]['timeout']}ms)")
                print(f"En yavaş proxy: {self.working_proxies[-1]['ip']}:{self.working_proxies[-1]['port']} ({self.working_proxies[-1]['timeout']}ms)")
        
        # Klavye dinleyicisini durdur
        self.keyboard_listener.stop()

    def split_proxy_list(self, proxies, part, total_parts):
        """Proxy listesini belirtilen parçaya böler.
        
        Args:
            proxies: Proxy listesi
            part: Kaçıncı parça (1'den başlar)
            total_parts: Toplam parça sayısı
        """
        if not proxies:
            return []
            
        chunk_size = len(proxies) // total_parts
        start_idx = (part - 1) * chunk_size
        end_idx = start_idx + chunk_size if part < total_parts else len(proxies)
        
        return proxies[start_idx:end_idx]

def combine_proxy_files():
    """Tüm parça dosyalarını birleştirir."""
    all_proxies = []
    
    # Ana dosyayı oku
    if os.path.exists('ssl_working_proxies.csv'):
        try:
            with open('ssl_working_proxies.csv', 'r', encoding='utf-8') as f:
                next(f)  # Başlık satırını atla
                for line in f:
                    ip, port, protocol, timeout = line.strip().split(',')
                    all_proxies.append({
                        'ip': ip,
                        'port': port,
                        'protocol': protocol,
                        'timeout': float(timeout)
                    })
            print(f"\nMevcut dosyadan {len(all_proxies)} proxy okundu.")
        except Exception as e:
            print(f"Ana dosya okunurken hata: {str(e)}")
    
    # Parça dosyalarını oku
    for i in range(1, 4):  # 3 parça için
        filename = f'ssl_working_proxies_part_{i}.csv'
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    next(f)  # Başlık satırını atla
                    part_proxies = []
                    for line in f:
                        ip, port, protocol, timeout = line.strip().split(',')
                        part_proxies.append({
                            'ip': ip,
                            'port': port,
                            'protocol': protocol,
                            'timeout': float(timeout)
                        })
                    print(f"{filename} dosyasından {len(part_proxies)} proxy okundu.")
                    all_proxies.extend(part_proxies)
            except Exception as e:
                print(f"{filename} okunurken hata: {str(e)}")
    
    # Tekrar eden proxy'leri temizle
    unique_proxies = {}
    for proxy in all_proxies:
        proxy_key = f"{proxy['ip']}:{proxy['port']}"
        if proxy_key not in unique_proxies or float(proxy['timeout']) < float(unique_proxies[proxy_key]['timeout']):
            unique_proxies[proxy_key] = proxy
    
    # Timeout'a göre sırala
    sorted_proxies = sorted(unique_proxies.values(), key=lambda x: float(x['timeout']))
    
    # Ana dosyaya kaydet
    with open('ssl_working_proxies.csv', 'w', encoding='utf-8', newline='') as f:
        f.write("ip,port,protocol,timeout\n")
        for proxy in sorted_proxies:
            f.write(f"{proxy['ip']},{proxy['port']},{proxy['protocol']},{proxy['timeout']}\n")
            
    print(f"\nToplam {len(sorted_proxies)} proxy birleştirildi!")
    if sorted_proxies:
        print("\nEn hızlı 3 proxy:")
        for i, proxy in enumerate(sorted_proxies[:3], 1):
            print(f"{i}. {proxy['protocol'].upper()}: {proxy['ip']}:{proxy['port']} ({proxy['timeout']}ms)")
    
    # Parça dosyalarını sil
    for i in range(1, 4):
        filename = f'ssl_working_proxies_part_{i}.csv'
        try:
            if os.path.exists(filename):
                os.remove(filename)
                print(f"{filename} silindi.")
        except Exception as e:
            print(f"{filename} silinirken hata: {str(e)}")

def main():
    print("1. URL'den Proxy Listesi Yükle")
    print("2. Dosyadan Proxy Listesi Yükle")
    print("3. CSV'deki Proxy'leri Test Et")
    print("4. Otomatik Bölünmüş Test")
    print("5. Parça Dosyalarını Birleştir")
    
    tester = ProxyTester()
    
    while True:
        try:
            secim = input("\nHangi modu kullanmak istiyorsunuz? (1-5): ")
            
            if secim == "1":
                saved_urls = tester.load_saved_urls()
                if saved_urls:
                    print("\nKaydedilmiş URL'ler:")
                    for i, url in enumerate(saved_urls, 1):
                        print(f"{i}. {url}")
                    
                    secim = input("\nKaydedilmiş URL'lerden birini seçin (numara) veya yeni URL girmek için 'Y' yazın: ")
                    if secim.lower() == 'y':
                        url = input("\nProxy listesi URL'sini girin: ")
                        tester.save_url(url)
                    else:
                        try:
                            url = saved_urls[int(secim) - 1]
                        except:
                            print("Geçersiz seçim! Yeni URL girişine yönlendiriliyorsunuz...")
                            url = input("\nProxy listesi URL'sini girin: ")
                            tester.save_url(url)
                else:
                    url = input("\nProxy listesi URL'sini girin: ")
                    tester.save_url(url)
                
                tester.proxy_url = url
                tester.run()
                break
                
            elif secim == "2":
                tester.run()
                break
                
            elif secim == "3":
                print("\nCSV'deki proxy'ler test ediliyor...")
                tester.test_csv_proxies()
                break
                
            elif secim == "4":
                saved_urls = tester.load_saved_urls()
                if saved_urls:
                    print("\nKaydedilmiş URL'ler:")
                    for i, url in enumerate(saved_urls, 1):
                        print(f"{i}. {url}")
                    
                    secim = input("\nKaydedilmiş URL'lerden birini seçin (numara) veya yeni URL girmek için 'Y' yazın: ")
                    if secim.lower() == 'y':
                        url = input("\nProxy listesi URL'sini girin: ")
                        tester.save_url(url)
                    else:
                        try:
                            url = saved_urls[int(secim) - 1]
                        except:
                            print("Geçersiz seçim! Yeni URL girişine yönlendiriliyorsunuz...")
                            url = input("\nProxy listesi URL'sini girin: ")
                            tester.save_url(url)
                else:
                    url = input("\nProxy listesi URL'sini girin: ")
                    tester.save_url(url)
                
                tester.proxy_url = url
                proxies = tester.load_proxies(url=url)
                
                if not proxies:
                    print("Proxy listesi yüklenemedi!")
                    break
                    
                print(f"\nToplam {len(proxies)} proxy bulundu.")
                print("3 terminal açılıyor...")
                
                # Her bölüm için ayrı bir terminal aç
                for part in range(1, 4):
                    split_proxies = tester.split_proxy_list(proxies, part, 3)
                    command = f"start cmd /k python proxy_tester.py --part {part} --total 3 --url {url}"
                    os.system(command)
                break
                
            elif secim == "5":
                print("\nParça dosyaları birleştiriliyor...")
                combine_proxy_files()
                break
                
            elif secim not in ["1", "2", "3", "4", "5"]:
                print("Lütfen 1-5 arası bir seçenek girin!")
                
        except Exception as e:
            print(f"Hata oluştu: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    # Komut satırı argümanlarını kontrol et
    parser = argparse.ArgumentParser()
    parser.add_argument('--part', type=int, help='Kaçıncı parça (1-3)')
    parser.add_argument('--total', type=int, help='Toplam parça sayısı')
    parser.add_argument('--url', type=str, help='Proxy listesi URL')
    args = parser.parse_args()
    
    if args.part and args.total:
        # Bölünmüş liste ile çalıştır
        tester = ProxyTester()
        tester.part_number = args.part  # Parça numarasını sakla
        tester.proxy_url = args.url
        proxies = tester.load_proxies(url=args.url)
        if proxies:
            split_proxies = tester.split_proxy_list(proxies, args.part, args.total)
            print(f"\n{len(split_proxies)} proxy test edilecek (Parça {args.part}/{args.total})")
            tester.working_proxies = []
            
            # Test edilecek proxy'leri güncelle ve çalıştır
            with ThreadPoolExecutor(max_workers=tester.max_workers) as executor:
                futures = []
                for proxy in split_proxies:
                    if tester.should_stop:
                        break
                    futures.append(executor.submit(tester.test_proxy, proxy))
                
                for future in as_completed(futures):
                    if tester.should_stop:
                        break
                    result = future.result()
                    if result:
                        tester.working_proxies.append(result)
                
            # Sonuçları parça dosyasına kaydet
            if tester.working_proxies:
                output_file = f'ssl_working_proxies_part_{args.part}.csv'
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    f.write("ip,port,protocol,timeout\n")
                    for proxy in sorted(tester.working_proxies, key=lambda x: float(x['timeout'])):
                        f.write(f"{proxy['ip']},{proxy['port']},{proxy['protocol']},{proxy['timeout']}\n")
                print(f"\nProxy'ler {output_file} dosyasına kaydedildi!")
    else:
        main()