# C Dependency Analyzer

C/C++ 프로젝트의 의존성을 분석하고 순환 참조를 탐지하여 Mermaid 다이어그램으로 시각화하는 도구

---

## 🚀 빠른 시작

```bash
# 기본 사용법
python Analyzer.py /path/to/project

# 특정 디렉토리 제외
python Analyzer.py /path/to/project --exclude build,test,vendor

# 통계 없이 다이어그램만
python Analyzer.py /path/to/project --no-stats

# 재귀 탐색 비활성화
python Analyzer.py /path/to/project --no-recursive
```

---

## 📊 주요 기능

### 1. 의존성 분석
- C/C++ 파일의 `#include "..."` 구문 파싱
- 모듈 간 의존성 그래프 생성
- Mermaid state diagram 출력

### 2. 순환 참조 탐지
- **Tarjan's SCC 알고리즘** 사용 (O(V+E) 선형 시간)
- 모든 순환 참조 그룹 발견
- 크기 순으로 정렬하여 출력

### 3. 순환 참조 분해 전략 제안
- **Bridge Modules**: 추출하기 좋은 모듈 식별
- **Weak Dependencies**: 제거하기 쉬운 의존성 찾기
- **Leaf Modules**: 분리 가능한 주변 모듈
- **Core Modules**: 함께 유지해야 할 핵심 모듈

---

## 📈 출력 예시

### Mermaid 다이어그램
```
stateDiagram-v2
    dev --> mgt
    mgt --> mlme
    mlme --> dev
    debug --> dev
```

### 통계 분석
```
============================================================
DEPENDENCY ANALYSIS RESULTS
============================================================

[>>] MOST REFERENCED MODULES (다른 모듈들이 가장 많이 참조하는 모듈)
------------------------------------------------------------
Rank   Module          Referenced By   Visual
------------------------------------------------------------
1      debug           51              ##############################
2      dev             44              ###########################---
3      mgt             35              #####################---------

[<<] MOST REFERENCING MODULES (가장 많은 모듈을 참조하는 모듈)
------------------------------------------------------------
Rank   Module          References      Visual
------------------------------------------------------------
1      dev             39              ##############################
2      mgt             28              ######################--------

[@] CIRCULAR DEPENDENCIES (순환 참조 - Strongly Connected Components)
------------------------------------------------------------
[!] Found 2 circular dependency group(s)
[!] Total 49 modules involved in cycles

1. SCC Group (Size: 47 modules)
   ----------------------------------------------------------------------
   Modules: ba <-> cac <-> cfg80211_ops <-> debug <-> dev <-> ...
   
   [BREAKING STRATEGY]
   
   Strategy 1: Extract Bridge Modules (모듈 추출)
   - These modules connect to external systems
   
     1. cfg80211_ops
        Internal: ←3 (in)  1→ (out) | External: ←0 (in)  1→ (out)
        Bridge Score: 0.20 (higher = better candidate)
     
     2. debug
        Internal: ←2 (in)  1→ (out) | External: ←0 (in)  1→ (out)
        Bridge Score: 0.25 (higher = better candidate)
   
   Strategy 2: Break Weak Dependencies (의존성 제거)
   - Remove these dependencies to break the cycle
   
     1. netif --> tx (impact: 4.00)
     2. tx --> netif (impact: 4.00)
   
   Strategy 3: Extract Leaf Modules (약한 결합 모듈)
   - These modules have fewer internal connections
   
     1. debug (internal: 3, external: 1)
   
   [CORE MODULES] - Keep these together
   - These are most central to the cycle
   
     1. dev (coupling: 9)
     2. mgt (coupling: 8)
     3. mlme (coupling: 6)

2. SCC Group (Size: 2 modules)
   ----------------------------------------------------------------------
   Modules: logger_core <-> logger_internal
   
   [BREAKING STRATEGY]
   ...
```

---

## 🎯 의존성 표기법 이해하기

### 표기 형식
```
Internal: ←2 (in)  1→ (out) | External: ←0 (in)  1→ (out)
```

### 의미 설명

| 항목 | 의미 | 예시 |
|------|------|------|
| **Internal ←2 (in)** | 순환 그룹 **내부**에서 이 모듈을 참조하는 개수 | `dev→debug, mlme→debug` |
| **Internal 1→ (out)** | 이 모듈이 순환 그룹 **내부**를 참조하는 개수 | `debug→dev` |
| **External ←0 (in)** | 순환 그룹 **외부**에서 이 모듈을 참조하는 개수 | 없음 |
| **External 1→ (out)** | 이 모듈이 순환 그룹 **외부**를 참조하는 개수 | `debug→procfs` |

### 시각적 예시
```
┌─────────────────────────────────┐
│  순환 참조 그룹 (Internal)     │
│                                  │
│    dev ──────┐                  │
│     ↑        │                  │
│     │        ↓                  │
│  debug ← mlme                   │  ← 분석 대상
│     │                            │
└─────┼────────────────────────────┘
      │
      └──→ procfs (External)
```

**debug 모듈**: `Internal: ←2 (in)  1→ (out) | External: ←0 (in)  1→ (out)`
- 내부 결합도 (Coupling): 2 + 1 = **3**
- 외부 연결 (Interface): 0 + 1 = **1**
- 브릿지 점수: 1/(3+1) = **0.25** → 추출 후보!

---

## 🔧 순환 참조 분해 전략

### Strategy 1: Bridge Modules (브릿지 모듈 추출)

**개념**: 외부와 많이 연결되고 내부와는 약하게 연결된 모듈

**식별 기준**:
- Bridge Score = Interface / (Coupling + 1)
- 높을수록 추출하기 좋음

**적용 방법**:
```c
// Before: cfg80211_ops가 순환 참조에 포함
dev.h → cfg80211_ops.h
mgt.h → cfg80211_ops.h
cfg80211_ops.h → dev.h, mgt.h  // 순환!

// After: 인터페이스 분리
// cfg80211_if.h (추상 인터페이스)
struct cfg80211_ops_if {
    int (*scan)(void *priv, ...);
    int (*connect)(void *priv, ...);
};

// 다른 모듈들은 인터페이스만 참조
#include "cfg80211_if.h"  // 구체적 구현체 참조 X
```

---

### Strategy 2: Break Weak Dependencies (약한 의존성 제거)

**개념**: 영향도가 낮은 의존성을 끊어서 순환 제거

**식별 기준**:
- Edge Impact = (Source Coupling + Target Coupling) / 2
- 낮을수록 제거하기 쉬움

**적용 방법**:
```c
// Before: 직접 참조
// netif.c
#include "tx.h"
void netif_send(packet_t *pkt) {
    tx_send_packet(pkt);  // 직접 호출
}

// After: 콜백 패턴
// netif.h
typedef void (*tx_handler_t)(packet_t *pkt);
void netif_register_tx(tx_handler_t handler);

// netif.c
static tx_handler_t g_tx_handler;

void netif_send(packet_t *pkt) {
    if (g_tx_handler)
        g_tx_handler(pkt);  // 콜백 호출
}

// tx.c (런타임에 등록)
void tx_init(void) {
    netif_register_tx(tx_send_packet);
}
```

---

### Strategy 3: Leaf Modules (리프 모듈 추출)

**개념**: 순환 그룹 내부에서 연결이 약한 "잎사귀" 모듈

**식별 기준**:
- Internal IN ≤ 1 또는 Internal OUT ≤ 1
- 한쪽 방향만 연결

**적용 방법**:
```c
// Before: debug가 순환 참조에 포함
dev → debug
mlme → debug
debug → dev  // 순환!

// After: 단방향 레이어링
[Infrastructure Layer]
  debug (로깅만 담당)
  
[Core Layer]
  dev → debug (단방향만)
  mlme → debug (단방향만)
```

---

### Core Modules (핵심 모듈 유지)

**개념**: 순환 그룹의 중심 - 함께 유지 권장

**식별 기준**:
- Coupling Score가 높음 (많은 내부 연결)
- 분리 시 영향이 큼

**대응 방안**:
- 핵심 모듈들은 하나의 "Core Layer"로 관리
- Layered Architecture 도입 고려

---

## 🎓 Tarjan's SCC 알고리즘

### 알고리즘 특징
- **시간 복잡도**: O(V + E) - 선형 시간
- **공간 복잡도**: O(V) - 선형 공간
- **완전성**: 모든 순환 참조 그룹 발견
- **효율성**: 단일 DFS 패스로 완료

### 성능 비교 (86 nodes, 475 edges)

| 알고리즘 | 시간 | 발견 | 특징 |
|---------|------|------|------|
| **Tarjan's SCC** | **0.20 ms** | **4 SCC** | ✅ 추천 |
| DFS (Simple) | ~0.05 ms | 사이클 있음 (Yes/No) | 단순 탐지만 |
| Johnson's | ~500 ms | 수백 개 경로 | ❌ 너무 느림 |

### 예상 시간

| 그래프 규모 | 예상 시간 |
|------------|----------|
| 1,000 nodes, 5,000 edges | ~2 ms |
| 10,000 nodes, 50,000 edges | ~21 ms |
| 100,000 nodes, 500,000 edges | ~211 ms |

### 핵심 개념

**SCC (Strongly Connected Component)**: 서로가 서로에게 도달 가능한 노드들의 집합

```
A → B → C → A  (하나의 SCC)
B → C → B      (같은 SCC)
C → A → C      (같은 SCC)

→ 세 개의 개별 사이클이 아닌, 하나의 SCC {A, B, C}로 보고
```

---

## 📋 실전 적용 순서

### Step 1: 분석 실행
```bash
python Analyzer.py /path/to/project --exclude build,test
```

### Step 2: 결과 해석
출력의 `[BREAKING STRATEGY]` 섹션 확인:
- **Bridge Modules**: 추출 후보 1순위
- **Weak Dependencies**: 제거 대상
- **Leaf Modules**: 분리 가능
- **Core Modules**: 함께 유지

### Step 3: 우선순위 결정

**Phase 1 (1-2주)**: 쉬운 것부터
- ✅ Bridge Module 1개 추출
- ✅ 테스트 통과 확인

**Phase 2 (2-3주)**: 중간 난이도
- ✅ Weak Edge 2-3개 제거
- ✅ 회귀 테스트

**Phase 3 (1-2개월)**: 본격 리팩토링
- ✅ Leaf Modules 추출
- ✅ Core Layer 정리

**Phase 4 (장기)**: 아키텍처 개선
- ✅ Layered Architecture 전환
- ✅ 전체 구조 재설계

### Step 4: 점진적 적용
```
⚠️ 중요: 한 번에 하나씩 변경하고 테스트!
```

---

## 💡 핵심 원칙

### 1. 의존성 방향
```
상위 레이어 → 하위 레이어 ✅
하위 레이어 ↛ 상위 레이어 ❌
```

### 2. 인터페이스 분리
```
구체적 구현 대신 추상 인터페이스에 의존
```

### 3. 단일 책임
```
하나의 모듈은 하나의 책임만
```

### 4. 점진적 개선
```
작은 변경 → 테스트 → 반복
Big Bang 리팩토링 금지!
```

---

## 📊 리팩토링 전후 비교

### Before
```
[거대한 순환 참조]
47개 모듈 ←→ 모두 연결됨

문제점:
❌ 테스트 어려움
❌ 컴파일 시간 증가
❌ 모듈 재사용 불가
❌ 버그 추적 복잡
```

### After (6개월 리팩토링 후)
```
[Layered Architecture]

Layer 3: API & Interface (3개 모듈)
  cfg80211_ops, nl80211_vendor, ioctl
  
Layer 2: Core Logic (15개 모듈)
  mgt, mlme, tx, rx, ba, cac, ...
  
Layer 1: Infrastructure (8개 모듈)
  dev, debug, netif, hip, ...
  
Utilities (5개 모듈)
  utils, log_clients, procfs, ...

개선 효과:
✅ 순환 참조 4개 → 0개
✅ 컴파일 시간 30% 감소
✅ 단위 테스트 가능
✅ 코드 이해도 향상
```

---

## 🔍 자주 묻는 질문

### Q: Bridge Score가 높다는 것은?
**A**: 외부 연결이 많고 내부 연결이 적다는 의미입니다. 이런 모듈은 순환 그룹에서 추출하기 쉽습니다.

### Q: Internal과 External의 기준은?
**A**: 순환 참조 그룹 내부/외부입니다. 같은 SCC에 속하면 Internal, 아니면 External입니다.

### Q: Core Modules는 어떻게 처리하나요?
**A**: 함께 유지하면서 Layered Architecture로 재구성하는 것을 권장합니다.

### Q: 모든 순환 참조를 제거해야 하나요?
**A**: 아닙니다. Core Layer 내부의 순환 참조는 허용 가능합니다. 중요한 것은 Layer 간 순환을 막는 것입니다.

### Q: 분석 시간이 얼마나 걸리나요?
**A**: 대부분의 프로젝트는 1초 미만입니다. 10만 노드 규모도 0.2초 정도입니다.

---

## 🛠️ 기술 스택

- **언어**: Python 3
- **알고리즘**: Tarjan's SCC (1972)
- **출력 형식**: Mermaid Diagram
- **의존성**: Python 표준 라이브러리만 사용

---

## 📝 옵션

```bash
python Analyzer.py <directory> [options]

Options:
  --no-recursive    재귀 탐색 비활성화
  --no-stats        통계 출력 생략
  --exclude         제외할 디렉토리 (쉼표 구분)

Example:
  python Analyzer.py ~/project --exclude build,test,vendor
```

---

## 🎯 사용 시나리오

### 1. 새 프로젝트 시작 전
```bash
# 레거시 코드 분석
python Analyzer.py /legacy/code

# 순환 참조 파악
# 리팩토링 계획 수립
```

### 2. 리팩토링 중
```bash
# Before
python Analyzer.py /code > before.txt

# [리팩토링 작업]

# After
python Analyzer.py /code > after.txt

# 개선 확인
diff before.txt after.txt
```

### 3. CI/CD 통합
```bash
# 순환 참조 검사
python Analyzer.py /code --no-stats > diagram.mmd

# 순환 참조가 늘었는지 체크
# 경고 또는 빌드 실패
```

---

## ⚠️ 제한사항

- `#include "..."` 형식만 분석 (시스템 헤더 `<...>` 제외)
- 조건부 컴파일(`#ifdef`)은 고려하지 않음
- 매크로 확장은 지원하지 않음
- C/C++ 언어만 지원

---

## 📚 참고 문헌

**Tarjan's Algorithm (1972)**
- Robert Tarjan, "Depth-first search and linear graph algorithms"
- SIAM Journal on Computing, Vol. 1, No. 2, 1972

**Design Patterns**
- Dependency Inversion Principle (SOLID)
- Layered Architecture Pattern
- Bridge Pattern

---

## 🤝 기여

버그 리포트, 기능 제안, Pull Request 환영합니다!

---

## 📄 라이센스

MIT License

---

## 🎉 Happy Refactoring!

순환 참조 없는 깨끗한 코드를 위해! 🚀
