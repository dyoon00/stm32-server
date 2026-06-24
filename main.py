from u_ads import ADS131M08
from u_csv import CSVWriter
import time


def main():
    ads = ADS131M08()

    try:
        ads.init()
        ads.start_capture()

        csv_writer = CSVWriter(ads.data_queue, 'data.csv')
        csv_writer.start()

        print("데이터 수신 중...")

        while True:
            time.sleep(1)
            print("-------------------------------------------")
            print(f"DRDY count  : {ads.drdy_count}")
            print(f"Frame count : {ads.frame_count}")
            print(f"Missed DRDY : {ads.missed_drdy}")
            print(f"CSV 저장    : {csv_writer.write_count}")
            print(f"Queue 크기  : {ads.data_queue.qsize()}")

    except KeyboardInterrupt:
        print("종료")
        csv_writer.stop()

    finally:
        ads.close()


if __name__ == "__main__":
    main()
