# 📡 Paper Radar

Type **keywords** and **key people**, press Enter, and get:

1. **New papers** on your topics (last 30 days, widened automatically when there are too few)
2. **New papers from the people you follow**
3. **Trends since 2020** — papers per year, yearly word clouds, rising topics
4. *(coming soon)* AI summaries sent weekly after your approval

Data: [OpenAlex](https://openalex.org) (CC0). Course project demo, Kyung Hee University.

---

## 실행 (로컬)

이 폴더(`paper_radar`)에서 실행해야 테마(`.streamlit/config.toml`)와 API 키(`secrets.toml`)가 적용됩니다.

```bash
.venv/Scripts/python -m streamlit run app.py
```

처음 설치할 때:

```bash
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## 배포 (Streamlit Community Cloud → 실제 URL)

1. GitHub에 새 저장소를 만듭니다 (예: `paper-radar`). 공개 저장소면 앱도 공개, 비공개면 비공개 앱(1개 제한)이 됩니다.
2. 이 폴더를 올립니다. `.gitignore`가 `.venv/`, `cache/`, `secrets.toml`을 빼 줍니다. **`seed_cache/`는 꼭 함께 올립니다.**
   ```bash
   git init -b main
   git add .
   git commit -m "Paper Radar demo"
   git remote add origin https://github.com/<아이디>/paper-radar.git
   git push -u origin main
   ```
3. https://share.streamlit.io → **Create app** → 저장소 `paper-radar`, 브랜치 `main`, 파일 `app.py`.
4. **App URL**에 원하는 이름 (예: `paper-radar-khu` → `https://paper-radar-khu.streamlit.app`).
5. **Advanced settings** → Python **3.12** 선택, **Secrets**에 아래를 붙여 넣기 → Deploy.
   ```toml
   OPENALEX_API_KEY = "발급받은_키"
   ```

### 클라우드 주의

- **API 키 필수.** 키가 없으면 OpenAlex 공유 한도(하루 $0.10)로 조회하는데, 클라우드 서버는 여러 앱이 IP를 나눠 쓸 가능성이 높아 금방 막힙니다. 무료 키: https://openalex.org/settings/api
- **12시간 동안 방문이 없으면 앱이 잠듭니다.** 발표 10분 전에 주소를 열어 깨워 두세요.
- 실행 중에 받은 결과(`cache/`)는 재시작하면 사라질 수 있습니다. 발표용 결과는 `seed_cache/`에 넣어 git으로 올립니다(아래).

## 발표 전 준비

1. **미리 받기** → `seed_cache/`에 저장 → git에 커밋·푸시
   ```bash
   .venv/Scripts/python prefetch.py
   ```
   다른 검색도 미리 받을 수 있습니다: `prefetch.py "network slicing, xApp" "Michele Polese"`
2. 주소로 바로 결과 열기 (링크 공유용):
   `https://<앱주소>/?kw=MAC+scheduler%2C+O-RAN&people=Tommaso+Melodia`
3. 네트워크가 불안하면 주소 끝에 `&offline=1` → 저장본만 사용.

화면 아래 표시로 데이터 출처를 알 수 있습니다: 🟢 Live · 🔵 Saved result · 🟠 OpenAlex busy (저장본 사용).

## 검색 규칙

| 입력 | 규칙 |
|---|---|
| Keywords | 쉼표로 구분, **쉼표 하나 = 반드시 포함할 주제 하나 (AND)**. 같은 뜻 표현은 자동 확장 (O-RAN = Open RAN = open radio access network, scheduler = scheduling 등, `core/query.py`의 `SYNONYMS`) |
| 기간 | 최근 30일 → 3편 미만이면 90일 → 365일로 자동 확장하고 화면에 알림 |
| Key people | 쉼표로 구분 (최대 3명). 논문 수가 가장 많은 동명 저자를 자동 선택, "Not the right person?"에서 변경 |
| 트렌드 | 키워드 중 **하나라도** 포함한 논문(OR)으로 넓게 집계. 검색어 자체는 워드클라우드에서 제외 |

## 파일

```
app.py              화면 전환 (URL ?kw=&people= 이 있으면 결과, 없으면 검색)
core/openalex.py    OpenAlex 조회, 요청 간격·재시도, 저장본(cache/, seed_cache/), 중복 제거
core/query.py       입력 해석, 동의어, 기간 자동 확장, 인물 매칭, 트렌드 집계
ui/style.py         디자인 (CSS, 상단 바, 히어로, 카드, 워드클라우드)
ui/search.py        검색 화면
ui/results.py       결과 화면 (01 New papers · 02 Key people · 03 Trends · 04 Summaries)
prefetch.py         발표·배포 전 미리 받기 → seed_cache/
.streamlit/config.toml   테마 (Agent1000 스타일 색·모서리·Inter 글꼴)
```

## 알려진 한계

- OpenAlex는 일부 출판사 논문의 초록이 비어 있어, 초록에만 나오는 표현은 놓칠 수 있습니다.
- 급상승 키워드는 연도별 상위 키워드 기준이라, 초기 연도에 순위 밖이던 단어는 증가 폭이 크게 보일 수 있습니다.
- 동명이인 자동 선택은 "논문 수 최다" 기준이라 틀릴 수 있습니다 → 화면에서 바꾸세요.
