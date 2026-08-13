# AI Agent 测试案例：银行交易系统模拟数据

> 数据源：DB Agent「连接管理」中的 **oracle-free 银行模拟库**（Oracle 26ai Free / `BANK` 用户 / `FREEPDB1`）
> 数据规模：机构 55、用户 2000、账户 2942、交易配置 25、业务流水 100000
> 数据锚点：`SYSDATE = 2026-08-12`，流水时间分布在前 365 天，期望值按此口径计算

## 使用方法

1. 在 DB Agent「AI 对话」中新建会话，数据源选择 **oracle-free 银行模拟库**
2. 逐个输入「提问」栏的自然语言问题
3. 对比 Agent 生成的 SQL 与「期望 SQL」、执行结果与「期望结果」
4. 判定标准：
   - 生成的 SQL 能否正确执行
   - 结果与期望值是否一致（时间窗口类允许口径差异，但应能从「近90天 / 本月」等措辞正确推导时间条件）
   - 是否合理使用 Oracle 方言（`TRUNC`、`ADD_MONTHS`、`FETCH FIRST`）

---

## 一、基础查询（L1）

### 案例 1：机构列表查询

- 测试点：单表查询、排序
- 提问：`查询所有机构，列出机构号、机构名称、机构层级和所在地区，按机构号排序`
- 期望 SQL：

```sql
SELECT ORG_ID, ORG_NAME, ORG_LEVEL, REGION
FROM T_ORG
ORDER BY ORG_ID;
```

- 期望结果：55 行；首行 `1 中国模拟银行总行 HEAD 北京`，末行 `330 中国模拟银行成都网点30 POINT 成都`

### 案例 2：风险客户数量

- 测试点：条件过滤、COUNT
- 提问：`一共有多少高风险客户？`
- 期望 SQL：

```sql
SELECT COUNT(*) FROM T_USER WHERE RISK_LEVEL = 'HIGH';
```

- 期望结果：`278`

### 案例 3：高余额账户

- 测试点：数值过滤
- 提问：`余额超过100万元的账户有多少个？`
- 期望 SQL：

```sql
SELECT COUNT(*) FROM T_ACCOUNT WHERE BALANCE > 1000000;
```

- 期望结果：`453`

---

## 二、聚合统计（L2）

### 案例 4：账户结构分布

- 测试点：GROUP BY + 平均余额
- 提问：`按账户类型统计账户数量和平均余额，按账户数量从多到少排列`
- 期望 SQL：

```sql
SELECT ACCOUNT_TYPE, COUNT(*), ROUND(AVG(BALANCE), 2)
FROM T_ACCOUNT
GROUP BY ACCOUNT_TYPE
ORDER BY COUNT(*) DESC;
```

- 期望结果：`SAVINGS 1368 / 254040.78`，`CHECKING 956 / 51725.15`，`FINANCE 276 / 1030648.26`，`CORP_BASIC 200 / 9904249.56`，`CORP_GEN 142 / 2381266.01`

### 案例 5：机构地区交易统计（近90天）

- 测试点：JOIN + 时间过滤 + GROUP BY + 排序
- 提问：`统计近90天各地区的成功交易笔数和交易金额，按金额从高到低`
- 期望 SQL：

```sql
SELECT o.REGION, COUNT(*), ROUND(SUM(l.AMOUNT), 2)
FROM T_TRANS_LOG l
JOIN T_ORG o ON o.ORG_ID = l.ORG_ID
WHERE l.STATUS = 'SUCCESS' AND l.TRANS_TIME >= TRUNC(SYSDATE) - 90
GROUP BY o.REGION
ORDER BY SUM(l.AMOUNT) DESC;
```

- 期望结果：成都 10154 笔 / 1,018,150,764；深圳 9299 笔 / 979,729,830；杭州 8547 笔 / 915,460,782；上海 9133 笔 / 909,613,021；广州 8602 笔 / 871,941,198；北京 8443 笔 / 838,528,978

### 案例 6：交易渠道分布

- 测试点：GROUP BY + 渠道维度
- 提问：`各交易渠道的成功交易笔数和金额分别是多少？`
- 期望 SQL：

```sql
SELECT CHANNEL, COUNT(*), ROUND(SUM(AMOUNT), 2)
FROM T_TRANS_LOG
WHERE STATUS = 'SUCCESS'
GROUP BY CHANNEL
ORDER BY COUNT(*) DESC;
```

- 期望结果：ONLINE 28012 笔、COUNTER 21859 笔、MOBILE 16401 笔、INTERNET 10079 笔、AUTO 8318 笔、ATM 7252 笔、POS 6536 笔（金额以执行结果为准）

---

## 三、时间窗口分析（L2-L3）

### 案例 7：近30天每日交易趋势

- 测试点：按天分组 + 日期截断
- 提问：`最近30天每天的成功交易笔数和金额，按日期排序`
- 期望 SQL：

```sql
SELECT TRUNC(TRANS_TIME) AS TRANS_DATE, COUNT(*), ROUND(SUM(AMOUNT), 2)
FROM T_TRANS_LOG
WHERE STATUS = 'SUCCESS' AND TRANS_TIME >= TRUNC(SYSDATE) - 29
GROUP BY TRUNC(TRANS_TIME)
ORDER BY TRANS_DATE;
```

- 期望结果：30 行，首日 `2026-07-14 / 607 笔 / 64,752,558`，末日 `2026-08-12 / 607 笔 / 55,382,925`

### 案例 8：本月交易汇总

- 测试点：月内时间过滤 + 聚合
- 提问：`这个月的成功交易有多少笔？总金额和平均金额是多少？`
- 期望 SQL：

```sql
SELECT COUNT(*), ROUND(SUM(AMOUNT), 2), ROUND(AVG(AMOUNT), 2)
FROM T_TRANS_LOG
WHERE STATUS = 'SUCCESS' AND TRANS_TIME >= TRUNC(SYSDATE, 'MM');
```

- 期望结果：`7165 笔 / 702,519,682 / 98,048.80`

### 案例 9：上月交易对比

- 测试点：月环比
- 提问：`上个月的成功交易笔数和总金额是多少？`
- 期望 SQL：

```sql
SELECT COUNT(*), ROUND(SUM(AMOUNT), 2)
FROM T_TRANS_LOG
WHERE STATUS = 'SUCCESS'
  AND TRANS_TIME >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
  AND TRANS_TIME < TRUNC(SYSDATE, 'MM');
```

- 期望结果：`18425 笔 / 1,896,339,844`

---

## 四、多表关联（L3）

### 案例 10：高余额客户 Top10

- 测试点：JOIN + ORDER BY + FETCH FIRST
- 提问：`余额最高的前10个有效账户，显示客户名称、账号、账户类型和余额`
- 期望 SQL：

```sql
SELECT u.USER_NAME, a.ACCOUNT_NO, a.ACCOUNT_TYPE, a.BALANCE
FROM T_ACCOUNT a
JOIN T_USER u ON u.USER_ID = a.USER_ID
WHERE a.STATUS = 'ACTIVE'
ORDER BY a.BALANCE DESC
FETCH FIRST 10 ROWS ONLY;
```

- 期望结果：Top3 为「新锐贸易有限公司 19,996,350」「启明建筑工程有限公司 19,981,446」「金诚信息技术有限公司 19,824,823」（均为 CORP_BASIC）

### 案例 11：客户交易活跃度（近90天 Top10）

- 测试点：JOIN + 时间过滤 + 分组排序
- 提问：`近90天交易总金额最高的前10个客户，显示客户名称、交易笔数和总金额`
- 期望 SQL：

```sql
SELECT u.USER_NAME, COUNT(*), ROUND(SUM(l.AMOUNT), 2)
FROM T_TRANS_LOG l
JOIN T_USER u ON u.USER_ID = l.USER_ID
WHERE l.STATUS = 'SUCCESS' AND l.TRANS_TIME >= TRUNC(SYSDATE) - 90
GROUP BY u.USER_NAME
ORDER BY SUM(l.AMOUNT) DESC
FETCH FIRST 10 ROWS ONLY;
```

- 期望结果：第1名「华信医疗器械有限公司 146 笔 / 17,278,240」，第7名「乔建 66 笔 / 14,077,110」（验证个人/企业客户混合排序）

### 案例 12：近30天最活跃机构 Top5

- 测试点：JOIN + 计数排序
- 提问：`最近30天交易笔数最多的前5家机构是哪些？`
- 期望 SQL：

```sql
SELECT o.ORG_NAME, COUNT(*)
FROM T_TRANS_LOG l
JOIN T_ORG o ON o.ORG_ID = l.ORG_ID
WHERE l.STATUS = 'SUCCESS' AND l.TRANS_TIME >= TRUNC(SYSDATE) - 29
GROUP BY o.ORG_NAME
ORDER BY COUNT(*) DESC
FETCH FIRST 5 ROWS ONLY;
```

- 期望结果：西湖支行 612、静安支行 554、拱墅支行 499、罗湖支行 476、锦江支行 466

---

## 五、复杂 / 风控场景（L3-L4）

### 案例 13：跨行转账手续费收入

- 测试点：按交易码过滤 + SUM
- 提问：`跨行转账一共收了多少手续费？成功了多少笔？`
- 期望 SQL：

```sql
SELECT COUNT(*), ROUND(SUM(FEE), 2)
FROM T_TRANS_LOG
WHERE TRANS_CODE = 'TRF_CROSS' AND STATUS = 'SUCCESS';
```

- 期望结果：`8208 笔 / 132,276.56`

### 案例 14：机构层级客户分布

- 测试点：JOIN + COUNT(DISTINCT)
- 提问：`按机构层级统计客户数量`
- 期望 SQL：

```sql
SELECT o.ORG_LEVEL, COUNT(DISTINCT u.USER_ID)
FROM T_USER u
JOIN T_ORG o ON o.ORG_ID = u.ORG_ID
GROUP BY o.ORG_LEVEL;
```

- 期望结果：BRANCH 49、SUB_BRANCH 820、POINT 1131（合计 2000）

### 案例 15：人均账户数

- 测试点：除法聚合
- 提问：`有效账户的人均账户数是多少？`
- 期望 SQL：

```sql
SELECT ROUND(COUNT(*) / COUNT(DISTINCT USER_ID), 2)
FROM T_ACCOUNT
WHERE STATUS = 'ACTIVE';
```

- 期望结果：`1.45`

### 案例 16：大额且活跃的客户数

- 测试点：多表 JOIN + 去重（考察 Agent 能否正确处理关联去重）
- 提问：`余额超过100万且近90天有成功交易的客户有多少个？`
- 期望 SQL：

```sql
SELECT COUNT(DISTINCT a.USER_ID)
FROM T_ACCOUNT a
JOIN T_TRANS_LOG l ON l.ACCOUNT_NO = a.ACCOUNT_NO
WHERE a.BALANCE > 1000000
  AND l.STATUS = 'SUCCESS'
  AND l.TRANS_TIME >= TRUNC(SYSDATE) - 90;
```

- 期望结果：`339`

### 案例 17：超限额交易排查（异常交易）

- 测试点：流水 JOIN 配置表 + 比较列
- 提问：`找出交易金额超过配置单笔限额的流水条数`
- 期望 SQL：

```sql
SELECT COUNT(*)
FROM T_TRANS_LOG l
JOIN T_TRANS_CONFIG c ON c.TRANS_CODE = l.TRANS_CODE
WHERE l.AMOUNT > c.SINGLE_LIMIT;
```

- 期望结果：`12241`（部分配置如代发工资单笔限额为 0，属模拟数据特征，可作为口径解释考察点）

### 案例 18：失败交易最多的账户

- 测试点：状态过滤 + Top-N
- 提问：`失败交易次数最多的前5个账号是哪些？`
- 期望 SQL：

```sql
SELECT ACCOUNT_NO, COUNT(*)
FROM T_TRANS_LOG
WHERE STATUS = 'FAIL'
GROUP BY ACCOUNT_NO
ORDER BY COUNT(*) DESC
FETCH FIRST 5 ROWS ONLY;
```

- 期望结果：首行 `626254892337048219 / 4 次`，其余 3 次（共 5 行）

### 案例 19：风险等级与交易规模

- 测试点：三表关联 + 分组聚合（高难度）
- 提问：`按客户风险等级统计成功交易的笔数和总金额`
- 期望 SQL：

```sql
SELECT u.RISK_LEVEL, COUNT(*), ROUND(SUM(l.AMOUNT), 2)
FROM T_TRANS_LOG l
JOIN T_USER u ON u.USER_ID = l.USER_ID
WHERE l.STATUS = 'SUCCESS'
GROUP BY u.RISK_LEVEL
ORDER BY SUM(l.AMOUNT) DESC;
```

- 期望结果：LOW 55446 笔 / 5,788,302,043；MEDIUM 29611 笔 / 3,003,310,954；HIGH 13400 笔 / 1,422,847,651

---

## 补充说明

- 数据可复现：生成脚本 `scripts/seed_oracle_bank.py` 随机种子固定为 `20260812`，重新生成后期望值不变
- 若修改 `BANK_N_USERS / BANK_N_TRANS` 重新生成数据，需重跑案例 SQL 更新期望值
- 建议按难度分轮次测试：先跑 L1-L2 验证基础能力，再跑 L3-L4 考察多表关联、去重和风控逻辑
- 时间窗口类用例依赖 `SYSDATE`，若服务器时间与 2026-08-12 相差较大，请先校准数据锚点或按新口径重算
