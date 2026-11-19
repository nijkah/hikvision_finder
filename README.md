# Hikvision Finder

Python 표준 라이브러리만 사용하는 **읽기 전용 Hikvision 장치 검색 CLI**입니다.
SADP 앱을 설치하지 않고 UDP 검색 요청으로 카메라·PoE 스위치 등의 MAC, IP,
모델, DHCP 여부, 활성화 상태를 확인합니다. IP 대역을 하나씩 스캔하지 않습니다.

## 적용 범위

- Hikvision SADP UDP inquiry에 응답하는 장치용이며 모든 제조사에 공통인 검색기는 아닙니다.
- 실제 Hikvision 카메라와 PoE 스위치에서 확인한 방식입니다. 모든 모델/펌웨어 지원을 보장하지 않습니다.
- PC와 장치는 검색 멀티캐스트가 전달되는 같은 로컬망/VLAN에 있어야 합니다.
  라우터, 무선 격리, 포트 격리, NVR 전용 PoE망 때문에 응답이 차단될 수 있습니다.
- DHCP가 꺼져 있거나 미활성인 장치도 응답할 수 있습니다. 검색 성공이 웹/RTSP 접속 성공을 뜻하지는 않습니다.
- IP 할당, DHCP 변경, 활성화, 비밀번호 변경, ARP 변경은 자동 수행하지 않습니다.

## 실행

Python 3.8 이상. pip 패키지는 필요 없습니다. macOS에서 실장비 검증했으며,
Linux는 `ip` 명령이 필요합니다. Windows 등에서는 `--local-ip`를 사용하세요
(macOS 외 환경은 실장비 검증하지 않았습니다).

```bash
git clone https://github.com/nijkah/hikvision_finder.git
cd hikvision_finder

# macOS: 유선 어댑터 이름 확인
networksetup -listallhardwareports

# en4는 예시이며 실제 유선 인터페이스 이름을 지정
python3 hikvision_finder.py --interface en4

# MAC으로 대상 필터링 (아래 MAC은 가상 예시)
python3 hikvision_finder.py -i en4 --mac 02:00:00:00:00:01

# 부팅 중인 장치에 더 긴 검색 시간 제공
python3 hikvision_finder.py -i en4 --timeout 30 --interval 3

# 인터페이스 이름 대신 내 PC 유선 IPv4 지정 (카메라 주소가 아님)
python3 hikvision_finder.py --local-ip 192.168.1.100

# Linux
python3 hikvision_finder.py -i eth0 --json
```

`--json` 출력은 `local_ip`, `devices`, `duplicate_ips`를 포함합니다.
장치는 MAC 기준으로 중복 제거하며, 동일 IP를 여러 MAC이 사용하면 경고합니다.
`--mac` 필터를 사용해도 IP 충돌 검사는 전체 응답을 기준으로 수행합니다.
응답에 없는 DHCP/활성화 값은 `unknown` (JSON에서는 `null`)입니다.

종료 코드: `0` 장치 발견, `1` 일치하는 응답 없음, `2` 입력/네트워크 오류,
`130` 사용자 중단. 응답 없음은 장치 부재의 확정 증거가 아닙니다.

## 새 카메라 설정 순서

1. 카메라에 PoE 또는 적절한 별도 전원을 공급하고 PC를 같은 망에 연결합니다.
2. 위 스크립트로 검색하고 라벨의 MAC/시리얼과 대조합니다.
3. 카메라 IP와 PC의 서브넷, IP 중복 여부를 확인합니다.
4. 카메라 웹페이지에서 필요하면 관리자 비밀번호를 만들어 활성화하고 DHCP를 켭니다.
5. DHCP 서버가 있는 망에서 다시 검색해 **동일 MAC**의 새 IP를 확인합니다.

DHCP가 꺼져 있어도 초기 고정 IP를 가질 수 있습니다. `169.254.x.x`는 필수 주소가
아니므로 이전 카메라의 주소를 새 장치에 그대로 적용하지 마세요.
내부망과 인터넷 Wi-Fi를 동시에 사용할 때는 macOS 네트워크 서비스 순서에서
Wi-Fi를 우선하도록 설정할 수 있습니다.

### macOS에서 초기 IP가 중복되는 경우

PC와 카메라가 같은 IPv4 서브넷에 있고 검색으로 대상 MAC을 확인했다면,
Mac에서 해당 IP의 목적지 MAC을 임시 지정해 접속할 수 있습니다.
**이것은 카메라에 IP를 할당하는 명령이 아닙니다.** 다른 프로그램의 해당 IP 접속에도
영향을 주므로 작업 후 반드시 제거하세요. 지속적인 통신 문제가 있으면 카메라를
별도 설정용 PoE 스위치/인젝터로 분리해 설정하세요.

아래 주소와 MAC은 예시입니다. 반드시 실제 검색 결과로 바꾸세요.

```bash
sudo arp -s 192.168.1.64 02:00:00:00:00:01 ifscope en4
arp -n 192.168.1.64
open http://192.168.1.64

# 웹에서 활성화 및 DHCP 저장 후, 또는 작업 취소 시 임시 지정 제거
sudo arp -d 192.168.1.64 ifscope en4

# 같은 MAC의 새 IP 조회
python3 hikvision_finder.py -i en4 --mac 02:00:00:00:00:01
```

## 검색 원리와 문제 해결

선택한 로컬 IPv4 인터페이스에서 `239.255.255.250:37020`으로 XML `Probe`
(`Types=inquiry`)를 반복 전송하고 UDP 37020의 `ProbeMatch` 응답을 파싱합니다.
관리자 권한은 일반적으로 필요하지 않으며 카메라 자격 증명도 사용하지 않습니다.

- 인터페이스에 IPv4가 없으면 전원·링크·PC 주소 설정부터 확인하세요.
- DHCP 서버가 없는 직결 환경에서는 IPv4 주소가 아직 없을 수 있습니다.
- macOS 로컬 네트워크 권한 및 방화벽의 UDP 37020/멀티캐스트 허용 상태를 확인하세요.
- 포트 바인딩 오류가 나면 다른 SADP/검색 프로그램을 종료하고 재시도하세요.
- Wi-Fi로 잘못 검색하지 않도록 `--interface` 또는 `--local-ip`를 명시합니다.
- 새 카메라 부팅을 기다린 뒤 `--timeout 30`으로 다시 검색하세요.
- 검색에는 카메라 외 Hikvision 스위치/NVR도 포함될 수 있으므로 모델명을 확인하세요.
- 결과에는 장치 MAC/시리얼/IP가 들어 있으므로 공개 이슈에 올릴 때는 필요한 값만 남기세요.

## 테스트

```bash
python3 -m unittest -v
```

테스트 데이터는 가상 MAC/IP를 사용합니다. 인증정보나 실장비 목록은 저장소에 포함하지 않습니다.
