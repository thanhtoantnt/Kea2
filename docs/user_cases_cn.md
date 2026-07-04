# Kea2的应用场景

Kea2不只关心“应用崩没崩”。它真正解决的是那些让测试团队头疼已久、却又一直没有好办法系统应对的问题：登录过不过得去？业务功能对不对？性能有没有劣化？测试脚本能不能少写80%？

下面的九个Kea2应用场景，覆盖了遍历测试、功能测试、性能测试三个方向。每个场景都来自真实项目中遇到的麻烦。

<table>
  <thead>
    <tr>
      <th>分类</th>
      <th>场景</th>
      <th>概括</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="4">遍历测试</td>
      <td>场景一：穿过登录等复杂入口</td>
      <td>用短脚本引导遍历工具通过登录页、表单页等"卡点"，进入有效业务空间</td>
    </tr>
    <tr>
      <td>场景二：跳出"焦油坑"页面</td>
      <td>识别并跳出 H5 页面、活动页、引导页等让工具困住打转的陷阱</td>
    </tr>
    <tr>
      <td>场景三：特定功能压测</td>
      <td>通过"目标检测+重入"脚本，把遍历范围锁定在指定业务模块内</td>
    </tr>
    <tr>
      <td>场景四：更易用的黑白名单</td>
      <td>支持 Activity、控件、区域三级黑名单，可设条件规则，控制探索边界</td>
    </tr>
    <tr>
      <td rowspan="4">功能测试</td>
      <td>场景五：在遍历中查找功能错误</td>
      <td>以性质为"测试预言"，让遍历不只发现崩溃，还能验证业务逻辑对错</td>
    </tr>
    <tr>
      <td>场景六：简化功能测试脚本</td>
      <td>只写核心操作+前置条件，无需手写冗长的到达和退出路径</td>
    </tr>
    <tr>
      <td>场景七：一个性质覆盖多个入口</td>
      <td>一次定义功能性质，自动覆盖不同入口、不同被转发对象等多样化场景</td>
    </tr>
    <tr>
      <td>场景八：让性质自动组合探索</td>
      <td>原子性质被随机组合，覆盖"新增+搜索""删除+重命名"等复杂操作路径</td>
    </tr>
    <tr>
      <td>性能测试</td>
      <td>场景九：指导遍历执行性能场景</td>
      <td>识别特定组件（如列表），自动执行滑动等操作并检测性能指标</td>
    </tr>
  </tbody>
</table>


接下来逐一展开九个场景的具体做法和代码示例。

## 场景一：遍历测试 - 穿过自动遍历难以越过的页面

很多App的关键功能依赖一些前置的特定操作。比如，在微信中，很多功能的测试需要先登陆，但登录页往往需要账号、密码、验证码、协议勾选等人工知识，纯随机遍历很难自然通过。同样的，火车票购买App需要输入一些合法目的地，这些功能的测试都需要依赖特定的人类知识或业务知识，难以被随机遍历工具执行。

<div align="center">
  <!-- 请将 src 替换为你的图片实际链接 -->
  <img src="https://github.com/user-attachments/assets/8e39cc38-5de0-4c71-ac73-a23e76381664" width="300" alt="登录示例">
  <br>
  <span style="color: #999; font-size: 12px;">示例：微信登陆页，需要填写特定用户名密码才能通过</span>
</div>

在Kea2中，我们可以利用性质解决这个问题，比如，在微信中，我们可以为登录页写一个很短的前置条件和交互脚本：

```python
# 前置条件 - 当前处于登陆页
@precondition(
    lambda self: self.d(text="请填写微信号/QQ号/邮箱").exists
    and self.d(text="请填写密码").exists
)
# 交互场景 - 执行登陆功能
def test_login(self):
    self.d(text="请填写微信号/QQ号/邮箱").set_text("username")
    self.d(text="请填写密码").set_text("password")
    self.d(text="同意并登录").click()
```

这段脚本不需要接管整个测试流程。它只是在Kea2探索到登录页时被触发，帮助自动遍历穿过这个关键卡点。登录之后，Fastbot可以继续探索更深的业务状态。

如果后续测试过程中应用意外退出登录，这段脚本也有机会再次被触发，继续把测试带回有效业务空间。

## 场景二：遍历测试 - 跳出“焦油坑”页面

自动遍历工具经常会陷入某些页面。例如多层H5页面、支付介绍页、引导页、活动页、复杂列表页。工具在里面反复点击、滑动，花费了大量时间却很难回到主业务路径。

<div align="center">
  <!-- 请将 src 替换为你的图片实际链接 -->
  <img src="https://github.com/user-attachments/assets/6f68c9f1-e0bc-4392-8afe-07f0464c9194" width="300" alt="焦油坑示例">
  <br>
  <span style="color: #999; font-size: 12px;">“焦油坑”示例：Keep的跑步页，需要长按解锁才能进行其他操作</span>
</div>

Kea2可以通过条件脚本帮助工具跳出这类页面。所谓条件脚本，就是给自动遍历过程添加一条“路标规则”：只有当页面满足某个特定条件时，脚本才会被触发执行，从而把探索方向拉回正轨——下面这段代码就是一个典型的例子：

```python
@prob(0.1)
@precondition(lambda self: self.d(text="解锁").exists)
def exit_lock_screen(self):
    self.d.long_click(text="解锁")
```

这段脚本的本质就是：当工具到了“解锁”页，以10%的概率尝试长按“解锁”离开。这就是一个带有业务判断的脱出指令——工具不再被困在页面上无限打转，而是有了一个明确的脱身策略。这里的核心在于：在识别到特定陷阱状态时，通过性质给定少量业务知识修正探索方向，降低遍历工具做的“无用功”。成本极低，效果立竿见影。

## 场景三：遍历测试 - 特定功能压测

对于一些业务逻辑复杂的APP而言，一个APP里会有多个子功能，每个业务线只负责一个子功能。比如飞书有即时消息、日历、云文档等等功能。

当特定业务团队实施遍历测试时，遍历测试往往会误跑到其他业务中去。

比如，我是飞书日历团队的工程师，我很关注日历相关功能的稳定性，但是遍历工具启动后，去隔壁的即时消息功能转了一圈又一圈，愣是没测我关注的日历功能。

Kea2可通过给定两个性质解决这个问题：“目标功能检测脚本”（检测当前是否在目标功能中，否则退出应用）与“目标功能重入脚本”（启动应用，进入目标功能）。

```python
def not_in_calendar_scenary(self: "LarkScenaryTest"):
    """判断不在飞书的“日历功能中”
    判断方法：前台activity不以calendar开头
    """
    cur_activity = self.d.app_current().get("activity")
    return "calendar" not in cur_activity

def restart_lark(self: "LarkScenaryTest"):
    """重启飞书
    """
    self.d.app_stop(LARK_PACKAGE)
    sleep(1)
    self.d.app_start(LARK_PACKAGE)
    sleep(1)

class LarkScenaryTest(TestCase):
    """飞书“日历”场景测试重入脚本集
    因为飞书日历有多个子功能，当发现不在“日历”场景中时，按概率随机进入一个子功能
    """
    d: Device

    @prob(0.3)
    @precondition(not_in_calendar_scenary)
    def test_calendar_settings(self):
        """进入日历设置功能"""
        print("Going to Lark settings")
        restart_lark(self)
        self.d(resourceId="com.ss.android.lark:id/textItem", text="日历").click()
        sleep(1)
        self.d(resourceId="com.ss.android.lark:id/sidebarEntrance").click()
        sleep(1)
        self.d(text="设置").click()
        sleep(1)
```

## 场景四： 遍历测试 - 更易使用的黑白名单

真实App测试中，测试人员往往需要控制探索边界。比如不希望点到危险按钮、不希望进入第三方包、不希望测试某些Activity，或者希望屏蔽某个UI区域。

Kea2为这个需求提供了更符合直觉的黑白名单指定方式。共支持Activity黑白名单、控件子树屏蔽（区域屏蔽）、控件屏蔽。

Kea2支持使用uiautomator2，通过指定控件节点的方式定义控件级和树级的黑名单：

* 可以屏蔽单个控件。
* 可以屏蔽一个控件及其整棵子树，也就是一个UI区域。
* 可以设置全局规则，也可以设置只在特定前置条件满足时生效的条件规则。

## 场景五：功能测试 - 在自动化遍历中查找功能错误

Kea2的核心能力之一，是在自动遍历中加入断言，以识别功能错误。

举个例子：一个社交App的视频通话功能，A给B打视频电话，结果接通的是语音——应用没有崩溃，日志也干干净净，但功能显然是错的。传统的遍历工具对此毫无感知，它只能看到“没崩溃”，看不到“应该出画面却出了声音”。

这类问题的本质，是自动化测试中一个老生常谈的难题——“测试预言”问题，即“什么样的应用行为是正确的”。崩溃和ANR的预言是显式的：应用卡死、抛出异常，工具一眼就能识别。但功能错误的预言隐藏在业务逻辑里，工具必须理解“视频”和“语音”分别意味着什么，才能判断对错。

而Kea2的做法，就是以性质为“测试预言”的载体——把判断标准交给对业务最熟悉的测试团队，让他们用性质描述功能应该是什么样，Kea2则在遍历过程中自动执行这些断言。这样一来，遍历测试的能力边界就从“发现崩溃”扩展到了“发现功能错误”。

## 场景六：功能测试 - 简化功能测试自动化脚本

我们可以在微信视频号中执行点赞功能：当页面上存在“喜欢”按钮时，点击之后状态应该变成“取消喜欢”，反之亦然。

这是个很简单的测试点，点赞和取消点赞只需要1步操作。但是，在传统自动化脚本中，为了测试这一个操作，我们还需要进行冗长的setup（从进入微信开始，编写路径到达视频号）和teardown（退出微信以保证下一个用例能顺利执行）操作：

<div align="center">
  <!-- 请将 src 替换为你的图片实际链接 -->
  <img src="https://github.com/user-attachments/assets/ce60c75f-1630-4201-8e5f-da5bf7947ef5" width="800" alt="简化功能测试脚本">
  <br>
</div>

但是，我们可以通过Kea2，使用断言功能，通过基于性质的测试完成对此功能对覆盖，具体而言，我们只编写“点赞和取消点赞这1步操作”，并制定性质执行的前置条件是：当前页面可点赞（“喜欢”按钮存在）

```python
@precondition(lambda self: self.d(description="喜欢").exists)
def test_finder_like(self):
    self.d(description="喜欢").click()
    assert self.d(description="取消喜欢").exists
```

测试人员不再需要手写“从首页进入视频号、找到某条视频、进入详情页”的完整路径。只要Fastbot探索到了存在点赞按钮的页面，这个性质就会被触发。

这也是Kea2和传统脚本测试很不一样的地方：它不是围绕特定的路径组织测试，而是围绕业务功能组织测试。

## 场景七：功能测试 - 一个性质覆盖多个自动化测试脚本

很多移动App中，同一个功能会出现在多个入口，想要测全，我们还需要检查不同路径下该功能是否正确。

例如“转发”功能可以转发不同的对象，如文本消息、图片、名片、位置、视频号内容等不同对象上。如果用传统脚本的思路，我们需要为每个入口编写一个用例。

<div align="center">
  <!-- 请将 src 替换为你的图片实际链接 -->
  <img src="https://github.com/user-attachments/assets/30a5b9e7-e808-44a8-8e44-9f2b05123e92" width="550" alt="微信“转发”操作">
  <br>
  <span style="color: #999; font-size: 12px;">微信“转发”操作示意图</span>
</div>

而Kea2的思路是：只要页面上存在“转发”入口，就可以验证转发动作本身是否正确。

```python
@precondition(
    lambda self: self.d(text="转发").exists
)
def test_forward(self):
    self.d(text="转发").click()
    assert self.d(text="选择聊天").exists
    assert self.d(text="创建新的聊天").exists
```

这样，一个性质就能覆盖多个业务入口。新增可转发对象时，只要转发逻辑不变，原有性质仍然可以继续发挥作用。

类似的，这个思想还特别适用于“SDK”类型功能的测试，比如，一个功能被多个业务集成，那么从不同的业务进入这个功能，功能的表现应该都是一致的。我们可以为这个功能维护一些性质，每有一个新业务集成时就可以复用这些性质进行测试。

## 场景八：功能测试 - 让性质自动组合，覆盖多样的测试路径

真实业务缺陷往往出现在操作组合之后。

比如通讯录标签功能中，单独测试“新增”“删除”“重命名”“搜索”并不难。难的是组合：

* 新增后搜索。  
* 新增后重命名再搜索。  
* 删除后再次搜索。 
* 多次新增、重命名、删除之后检查列表状态。

<div align="center">
  <!-- 请将 src 替换为你的图片实际链接 -->
  <img src="https://github.com/user-attachments/assets/9be950d4-fdfa-46d9-a798-c5f22bd24db5" width="800" alt="性质组合示例">
  <br>
</div>

传统脚本如果要覆盖这些路径，需要手动编排大量组合，这样的组合无穷无尽。但是，Kea2则可以把每个原子功能写成独立性质，让工具在探索过程中随机组合它们。

也就是说，你可以分别定义新增、删除、重命名、搜索四个性质。Kea2在运行中会把它们组合成更多路径，从而扩大业务状态空间的覆盖。

当测试需要跨性质共享数据时，Kea2还提供`state`对象。比如新增标签后记录标签名，后续搜索或删除性质可以复用这个状态，进一步支持带状态测试。

## 场景九： 性能测试 - 用性质指导遍历，检测关注的性能场景

在性能测试中，我们往往会关注某些组件的特定操作是否会有性能问题。比如，某个列表滑动时会不会卡顿？上滑页面刷新加载时长会不会太长？

<div align="center">
  <!-- 请将 src 替换为你的图片实际链接 -->
  <img src="https://github.com/user-attachments/assets/4122dee7-2db7-414a-b32d-bd3af7d206e7" width="300" alt="知乎上滑刷新操作">
  <br>
  <span style="color: #999; font-size: 12px;">示例：知乎上滑刷新操作</span>
</div>

这些性能测试点都依赖特定的操作，普通的模糊测试工具很少注入相应的操作。为此，我们可以使用Kea2编写相关性质，识别到列表时往列表中注入相关的操作，以实现对列表滑动相关性能的场景执行及性能检测。

```python
@precondition(
    lambda self: self.d(description="首页列表").exists
)
def test_forward(self):
    self.start_perf()
    self.swipe(description="首页列表").swipe("up")
    self.stop_perf()
    # assert 刷新耗时满足性能要求
    assert self.refresh_call_cost < 100
```
