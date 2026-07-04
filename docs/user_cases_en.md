# Kea2 Use Cases

Kea2 is not only concerned with whether an app crashes. It addresses problems that have long troubled testing teams but have been difficult to handle systematically: Can the login flow be passed? Is the business logic correct? Has performance degraded? Can we write 80% fewer test scripts?

The following nine Kea2 use cases cover three areas: exploration testing, functional testing, and performance testing. Every case comes from real problems encountered in actual projects.

<table>
  <thead>
    <tr>
      <th>Category</th>
      <th>Case</th>
      <th>Summary</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="4">Exploration Testing</td>
      <td>Case 1: Passing through complex entry points such as login</td>
      <td>Use short scripts to guide the exploration tool through "blocking points" such as login pages and form pages, bringing it into valid business states</td>
    </tr>
    <tr>
      <td>Case 2: Escaping "tarpit" pages</td>
      <td>Identify and escape traps such as H5 pages, campaign pages, and onboarding pages where the tool may get stuck repeatedly</td>
    </tr>
    <tr>
      <td>Case 3: Stress testing specific features</td>
      <td>Use "target detection + re-entry" scripts to lock the exploration scope inside a specified business module</td>
    </tr>
    <tr>
      <td>Case 4: Easier-to-use blacklists and whitelists</td>
      <td>Support Activity-, widget-, and region-level blacklists, with conditional rules to control exploration boundaries</td>
    </tr>
    <tr>
      <td rowspan="4">Functional Testing</td>
      <td>Case 5: Finding functional bugs during exploration</td>
      <td>Use properties as "test oracles" so exploration can not only find crashes, but also verify whether business logic is correct</td>
    </tr>
    <tr>
      <td>Case 6: Simplifying functional test scripts</td>
      <td>Write only the core action plus a precondition, without manually scripting long setup and teardown paths</td>
    </tr>
    <tr>
      <td>Case 7: Covering multiple entry points with one property</td>
      <td>Define a functional property once and automatically cover diverse scenarios such as different entry points and different forwarded objects</td>
    </tr>
    <tr>
      <td>Case 8: Letting properties combine automatically during exploration</td>
      <td>Randomly combine atomic properties to cover complex operation paths such as "create + search" and "delete + rename"</td>
    </tr>
    <tr>
      <td>Performance Testing</td>
      <td>Case 9: Guiding exploration to execute performance scenarios</td>
      <td>Identify specific components, such as lists, automatically execute actions such as swipes, and check performance metrics</td>
    </tr>
  </tbody>
</table>


Next, we will walk through the concrete methods and code examples for these nine scenarios.

## Case 1: Exploration Testing - Passing Through Pages That Automatic Exploration Struggles to Cross

Many important app features depend on specific prerequisite actions. For example, in WeChat, many features require the user to log in first, but login pages often require human or business knowledge such as account names, passwords, verification codes, and agreement checkboxes. Pure random exploration can hardly pass through them naturally. Similarly, train-ticket purchasing apps require valid destinations. These features depend on specific human knowledge or business knowledge, making them difficult for random exploration tools to execute.

<div align="center">
  <!-- Replace src with the actual image link -->
  <img src="https://github.com/user-attachments/assets/8e39cc38-5de0-4c71-ac73-a23e76381664" width="300" alt="Login example">
  <br>
  <span style="color: #999; font-size: 12px;">Example: WeChat login page, which requires specific username and password input to pass</span>
</div>

In Kea2, we can use properties to solve this problem. For example, in WeChat, we can write a very short precondition and interaction script for the login page:

```python
# Precondition - currently on the login page
@precondition(
    lambda self: self.d(text="请填写微信号/QQ号/邮箱").exists
    and self.d(text="请填写密码").exists
)
# Interaction scenario - perform login
def test_login(self):
    self.d(text="请填写微信号/QQ号/邮箱").set_text("username")
    self.d(text="请填写密码").set_text("password")
    self.d(text="同意并登录").click()
```

This script does not need to take over the entire testing process. It is triggered only when Kea2 explores to the login page, helping automatic exploration pass through this key blocking point. After login, Fastbot can continue exploring deeper business states.

If the app unexpectedly logs out during later testing, this script also has a chance to be triggered again, bringing the test back into a valid business space.
## Case 2: Exploration Testing - Escaping "Tarpit" Pages

Automatic exploration tools often get stuck on certain pages, such as multi-level H5 pages, payment introduction pages, onboarding pages, campaign pages, and complex list pages. The tool repeatedly clicks and swipes inside them, spending a large amount of time while struggling to return to the main business path.

<div align="center">
  <!-- Replace src with the actual image link -->
  <img src="https://github.com/user-attachments/assets/6f68c9f1-e0bc-4392-8afe-07f0464c9194" width="300" alt="Tar pit example">
  <br>
  <span style="color: #999; font-size: 12px;">A "tarpit" example: Keep's running page, where users must long-press to unlock before performing other actions</span>
</div>

Kea2 can use conditional scripts to help the tool escape these pages. A conditional script adds a "road sign rule" to automatic exploration: only when the page satisfies a specific condition will the script be triggered, pulling the exploration direction back on track. The following code is a typical example:

```python
@prob(0.1)
@precondition(lambda self: self.d(text="解锁").exists)
def exit_lock_screen(self):
    self.d.long_click(text="解锁")
```

The essence of this script is: when the tool reaches the "unlock" page, it has a 10% probability of trying to long-press "unlock" to leave. This is an escape instruction with business judgment—the tool no longer spins endlessly on the page, but has a clear strategy for getting out. The key idea is to recognize a specific trap state and use a property to provide a small amount of business knowledge that corrects the exploration direction, reducing the tool's "wasted work". The cost is very low, and the effect is immediate.

## Case 3: Exploration Testing - Stress Testing Specific Features

For apps with complex business logic, one app may contain multiple sub-features, and each business team may be responsible for only one sub-feature. For example, Lark includes instant messaging, calendar, cloud documents, and many other features.

When a specific business team runs exploration testing, the exploration test may often wander into other business areas.

For example, suppose I am an engineer on the Lark Calendar team and I care about the stability of calendar-related features. After the exploration tool starts, however, it keeps wandering around the neighboring instant messaging feature and barely tests the calendar features I care about.

Kea2 can solve this problem by defining two properties: a "target feature detection script" that checks whether the current state is inside the target feature and exits the app otherwise, and a "target feature re-entry script" that starts the app and enters the target feature.

```python
def not_in_calendar_scenary(self: "LarkScenaryTest"):
    """Determine whether the current state is outside Lark's "Calendar" feature.
    Method: the foreground activity does not start with calendar.
    """
    cur_activity = self.d.app_current().get("activity")
    return "calendar" not in cur_activity

def restart_lark(self: "LarkScenaryTest"):
    """Restart Lark.
    """
    self.d.app_stop(LARK_PACKAGE)
    sleep(1)
    self.d.app_start(LARK_PACKAGE)
    sleep(1)

class LarkScenaryTest(TestCase):
    """Re-entry script set for Lark's "Calendar" scenario.
    Because Lark Calendar has multiple sub-features, when the test detects
    that it is outside the "Calendar" scenario, it randomly enters one
    sub-feature according to probability.
    """
    d: Device

    @prob(0.3)
    @precondition(not_in_calendar_scenary)
    def test_calendar_settings(self):
        """Enter the calendar settings feature."""
        print("Going to Lark settings")
        restart_lark(self)
        self.d(resourceId="com.ss.android.lark:id/textItem", text="日历").click()
        sleep(1)
        self.d(resourceId="com.ss.android.lark:id/sidebarEntrance").click()
        sleep(1)
        self.d(text="设置").click()
        sleep(1)
```

## Case 4: Exploration Testing - Easier-to-Use Blacklists and Whitelists

In real app testing, testers often need to control exploration boundaries. For example, they may not want to tap dangerous buttons, enter third-party packages, test certain Activities, or may want to block a specific UI region.

Kea2 provides a more intuitive way to specify blacklists and whitelists for this need. It supports Activity blacklists and whitelists, widget subtree blocking (region blocking), and widget blocking.

Kea2 supports uiautomator2 and allows users to define widget-level and tree-level blacklists by specifying widget nodes:

* A single widget can be blocked.
* A widget and its entire subtree can be blocked, which means a UI region can be blocked.
* Global rules can be set, and conditional rules can also be set to take effect only when specific preconditions are satisfied.

## Case 5: Functional Testing - Finding Functional Bugs During Automatic Exploration

One of Kea2's core capabilities is adding assertions to automatic exploration to identify functional bugs.

For example, in a social app's video call feature, user A makes a video call to user B, but the call connects as a voice call. The app does not crash, and the logs look clean, but the function is clearly wrong. Traditional exploration tools are unaware of this. They can only see "no crash"; they cannot see that "video should appear, but only audio appeared".

The essence of this problem is a classic challenge in automated testing: the "test oracle" problem, namely, "what kind of app behavior is correct". Crash and ANR oracles are explicit: the app freezes or throws an exception, and the tool can recognize it immediately. But functional bug oracles are hidden in business logic. The tool must understand what "video" and "voice" respectively mean before it can judge correctness.

Kea2's approach is to use properties as the carrier of "test oracles": the testing team that understands the business best describes what the function should look like with properties, and Kea2 automatically executes these assertions during exploration. In this way, the boundary of exploration testing expands from "finding crashes" to "finding functional bugs".

## Case 6: Functional Testing - Simplifying Functional Test Automation Scripts

We can test the like feature in WeChat Channels: when the "Like" button exists on the page, clicking it should change the state to "Unlike", and vice versa.

This is a very simple test point. Liking and unliking require only one operation. However, in traditional automation scripts, to test this single operation, we still need lengthy setup operations (starting from WeChat and scripting the path to reach Channels) and teardown operations (exiting WeChat to ensure that the next test case can run smoothly):

<div align="center">
  <!-- Replace src with the actual image link -->
  <img src="https://github.com/user-attachments/assets/ce60c75f-1630-4201-8e5f-da5bf7947ef5" width="800" alt="Simplifying functional test scripts">
  <br>
</div>

With Kea2, however, we can use assertions and property-based testing to cover this feature. Specifically, we only write the one-step operation of "like and unlike", and define the property's precondition as: the current page is likeable (the "Like" button exists).

```python
@precondition(lambda self: self.d(description="喜欢").exists)
def test_finder_like(self):
    self.d(description="喜欢").click()
    assert self.d(description="取消喜欢").exists
```

Testers no longer need to manually write the complete path of "enter Channels from the home page, find a video, and open its detail page". As long as Fastbot explores to a page with a like button, this property will be triggered.

This is also a key difference between Kea2 and traditional script testing: it organizes tests around business functions rather than specific paths.

## Case 7: Functional Testing - Covering Multiple Automation Test Scripts with One Property

In many mobile apps, the same function appears at multiple entry points. To test it thoroughly, we need to check whether the function behaves correctly under different paths.

For example, the "forward" function can forward different objects, such as text messages, images, contact cards, locations, and Channels content. With traditional scripting, we would need to write one test case for each entry point.

<div align="center">
  <!-- Replace src with the actual image link -->
  <img src="https://github.com/user-attachments/assets/30a5b9e7-e808-44a8-8e44-9f2b05123e92" width="550" alt="WeChat forward operation">
  <br>
  <span style="color: #999; font-size: 12px;">Illustration of the WeChat "forward" operation</span>
</div>

Kea2's idea is that as long as a "forward" entry point exists on the page, we can verify whether the forwarding action itself is correct.

```python
@precondition(
    lambda self: self.d(text="转发").exists
)
def test_forward(self):
    self.d(text="转发").click()
    assert self.d(text="选择聊天").exists
    assert self.d(text="创建新的聊天").exists
```

In this way, one property can cover multiple business entry points. When new forwardable objects are added, as long as the forwarding logic remains unchanged, the original property can continue to work.

Similarly, this idea is especially suitable for testing SDK-style features. For example, if one feature is integrated by multiple businesses, then the feature's behavior should be consistent no matter which business enters it. We can maintain a set of properties for this feature, and reuse these properties whenever a new business integrates it.

## Case 8: Functional Testing - Letting Properties Combine Automatically to Cover Diverse Test Paths

Real business defects often appear after combinations of operations.

For example, in a contact tag feature, it is not difficult to test "create", "delete", "rename", and "search" individually. The difficulty lies in combinations:

* Search after creating.  
* Search after creating and then renaming.  
* Search again after deleting. 
* Check the list state after multiple creates, renames, and deletes.

<div align="center">
  <!-- Replace src with the actual image link -->
  <img src="https://github.com/user-attachments/assets/9be950d4-fdfa-46d9-a798-c5f22bd24db5" width="800" alt="Property combination example">
  <br>
</div>

If traditional scripts need to cover these paths, testers must manually arrange a large number of combinations, and such combinations are endless. Kea2, however, can write each atomic function as an independent property and let the tool randomly combine them during exploration.

In other words, you can define four properties for create, delete, rename, and search respectively. During execution, Kea2 combines them into more paths, thereby expanding coverage of the business state space.

When tests need to share data across properties, Kea2 also provides a `state` object. For example, after creating a tag, the tag name can be recorded, and later search or delete properties can reuse this state, further supporting stateful testing.

## Case 9: Performance Testing - Using Properties to Guide Exploration and Check Performance Scenarios of Interest

In performance testing, we often care about whether specific operations on certain components have performance problems. For example, does scrolling a list cause jank? Does pull-up refresh take too long?

<div align="center">
  <!-- Replace src with the actual image link -->
  <img src="https://github.com/user-attachments/assets/4122dee7-2db7-414a-b32d-bd3af7d206e7" width="300" alt="Zhihu pull-up refresh operation">
  <br>
  <span style="color: #999; font-size: 12px;">Example: Zhihu pull-up refresh operation</span>
</div>

These performance test points all depend on specific operations, and ordinary fuzzing tools rarely inject the corresponding operations. Therefore, we can use Kea2 to write related properties. When a list is recognized, Kea2 injects the relevant operations into the list, enabling execution and performance checking for list-scrolling-related scenarios.

```python
@precondition(
    lambda self: self.d(description="首页列表").exists
)
def test_forward(self):
    self.start_perf()
    self.swipe(description="首页列表").swipe("up")
    self.stop_perf()
    # assert that refresh latency meets the performance requirement
    assert self.refresh_call_cost < 100
```
