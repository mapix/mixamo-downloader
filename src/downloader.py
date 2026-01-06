# Stdlib modules
import json
import os
import requests
import time
import logging
from datetime import datetime

# Third-party modules
from PySide2 import QtCore, QtWebEngineWidgets, QtWidgets

# 配置日志
log_filename = f"mixamo_downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


HEADERS = {
"Accept": "application/json",
"Accept-Encoding":"gzip, deflate, br, zstd",
"Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
"Content-Type": "application/json",
"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
"Referer": "https://www.mixamo.com/",
"Origin": "https://www.mixamo.com",
"X-Api-Key": "mixamo2",
"X-Requested-With": "XMLHttpRequest",
}

# All requests will be done through a session to improve performance.
session = requests.Session()


class MixamoDownloader(QtCore.QObject):
  """Bulk download animations from Mixamo.

  Users can choose to download all animations in Mixamo (quite slow),
  only those that contain a specific word (faster), or just the T-Pose.

  The download mode is to be passed onto this class as an argument
  when creating an instance.

  The first step is to get the primary character ID and name.


  """
  # Create signals that will be used to emit info to the UI.
  finished = QtCore.Signal()
  total_tasks = QtCore.Signal(int)
  current_task = QtCore.Signal(int)

  # Initialize a counter for the progress bar.
  task = 1
  
  # Initialize a flag that tells the code to stop.
  stop = False

  def __init__(self, path, mode, query=None, proxy=None, delay=0.5):
    """Initialize the Mixamo Downloader object.

    :param path: Output folder path
    :type path: str

    :param mode: Download mode ("all", "query" or "tpose")
    :type mode: str

    :param query: Keyword to be used as query when searching animations
    :type query: str
    
    :param proxy: HTTP proxy URL (e.g., "http://127.0.0.1:7890")
    :type proxy: str
    
    :param delay: Delay in seconds between requests to avoid rate limiting
    :type delay: float
    """
    super().__init__()

    self.path = path
    self.mode = mode
    self.query = query
    self.proxy = proxy
    self.delay = delay
    
    # Configure proxy for the session if provided
    if self.proxy:
      session.proxies = {
        'http': self.proxy,
        'https': self.proxy
      }
      
      logging.info(f"使用代理: {self.proxy}")
      
      # Test proxy connection
      try:
        logging.info("正在测试代理连接...")
        test_response = session.get("https://www.mixamo.com", timeout=10)
        if test_response.status_code in [200, 301, 302]:
          logging.info("✅ 代理连接测试成功")
        else:
          logging.warning(f"⚠️ 代理返回状态码: {test_response.status_code}")
      except Exception as e:
        logging.warning(f"⚠️ 代理测试失败: {str(e)[:100]}")
    else:
      session.proxies = {}
      logging.info("直连模式（无代理）")

  def _request_get(self, url, headers=None, timeout=30):
    """统一的 GET 请求方法"""
    return session.get(url, headers=headers, timeout=timeout)
  
  def _request_post(self, url, json_data=None, headers=None, timeout=60):
    """统一的 POST 请求方法"""
    return session.post(url, json=json_data, headers=headers, timeout=timeout)
  
  def _download_file(self, url, file_path, timeout=120):
    """统一的文件下载方法"""
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    with open(file_path, 'wb') as f:
      f.write(response.content)
    return {'success': True, 'size': len(response.content)}

  def run(self):
    logging.info("="*60)
    logging.info("开始下载任务")
    logging.info(f"下载模式: {self.mode}")
    logging.info(f"输出路径: {self.path if self.path else '当前目录'}")
    if self.query:
      logging.info(f"搜索关键词: {self.query}")
    logging.info(f"请求延迟: {self.delay} 秒")
    logging.info("="*60)
    
    # Get the primary character ID and name.
    character_id = self.get_primary_character_id()
    character_name = self.get_primary_character_name()
    
    # If there's no character ID, it means that there was some problem
    # with the access token, so we better stop the code at this point. 
    if not character_id:
      logging.error("无法获取角色ID，请检查是否已登录Mixamo")
      return
    
    logging.info(f"角色名称: {character_name}")
    logging.info(f"角色ID: {character_id}")

    # DOWNLOAD MODE: TPOSE
    if self.mode == "tpose":
      # The total amount of tasks to process is 1.
      self.total_tasks.emit(1)

      # Build the T-Pose payload.
      tpose_payload = self.build_tpose_payload(character_id, character_name)

      # Check if file already exists BEFORE exporting
      if self.path:
        if not os.path.exists(self.path):
          os.makedirs(self.path, exist_ok=True)
        file_path = f"{self.path}/{self.product_name}.fbx"
      else:
        file_path = f"{self.product_name}.fbx"
      
      if os.path.exists(file_path):
        file_size = os.path.getsize(file_path) / 1024  # KB
        logging.info(f"⏭️  T-Pose 已存在，跳过: {self.product_name} ({file_size:.2f} KB)")
        self.current_task.emit(self.task)
        self.finished.emit()
        return

      # Export and download the T-Pose.
      url = self.export_animation(character_id, tpose_payload)

      #print(f"Downloading T-Pose (with skin) for {character_name}...")
      self.download_animation(url)
      #print(f"T-Pose successfully downloaded.")

      # Emit the 'finished' signal to let the UI know that worker is done.
      self.finished.emit()
      return

    # DOWNLOAD MODE: ALL
    if self.mode == "all":
      # Get animation IDs from the JSON file on disk.
      anim_data = self.get_all_animations_data()

    # DOWNLOAD MODE: QUERY
    elif self.mode == "query":
      # Search for animation IDs according to the query entered by the user.
      anim_data = self.get_queried_animations_data(self.query)

    # Check if we got any animations
    if not anim_data:
      logging.error("❌ 无法获取动画列表，程序终止")
      self.finished.emit()
      return

    # The following code will be run for both the "all" and "query" modes.
    logging.info(f"总共需要下载 {len(anim_data)} 个动画")
    
    # Iterate the animation IDs and names dictionary.
    for idx, (anim_id, anim_name) in enumerate(anim_data.items(), 1):

      # Check if the 'Stop' button has been pressed in the UI.
      if self.stop:
        logging.info("用户停止了下载")
        # Let the thread know that the worker has finished the job.
        # Stopping the function here with a return makes the thread actually
        # finish. Without it, the thread would remain active until every line
        # of this method is done.
        self.finished.emit()
        return

      logging.info(f"[{idx}/{len(anim_data)}] 处理动画: {anim_name} (ID: {anim_id})")
      
      try:
        # Build the animation payload, export and download it to disk.
        anim_payload = self.build_animation_payload(character_id, anim_id)
        
        # If payload building failed, skip this animation
        if not anim_payload:
          logging.warning(f"⚠️  跳过动画（无法构建payload）: {anim_name}")
          self.current_task.emit(self.task)
          self.task += 1
          continue
        
        # Check if file already exists BEFORE exporting (to save API quota)
        # self.product_name is set by build_animation_payload
        if self.path:
          if not os.path.exists(self.path):
            os.makedirs(self.path, exist_ok=True)
          file_path = f"{self.path}/{self.product_name}.fbx"
        else:
          file_path = f"{self.product_name}.fbx"
        
        if os.path.exists(file_path):
          file_size = os.path.getsize(file_path) / 1024  # KB
          logging.info(f"⏭️  跳过已存在的文件: {self.product_name} ({file_size:.2f} KB)")
          # Update progress bar
          self.current_task.emit(self.task)
          self.task += 1
          # Add a small delay even for skipped files
          if self.delay > 0:
            time.sleep(min(0.1, self.delay))
          continue
        
        url = self.export_animation(character_id, anim_payload)

        #print(f"Downloading {anim_name}...")
        self.download_animation(url)
        
        # Add delay between animations to avoid rate limiting (429 errors)
        if self.delay > 0:
          time.sleep(self.delay)
          
      except Exception as e:
        logging.error(f"❌ 处理动画时发生异常: {anim_name}, 错误: {str(e)}")
        # 确保进度条继续更新
        self.current_task.emit(self.task)
        self.task += 1
        continue

    logging.info("="*60)
    logging.info("所有下载任务完成！")
    logging.info("="*60)
    # Emit the 'finished' signal to let the UI know that worker is done.
    self.finished.emit()
    return

  def get_primary_character_id(self):
    """Get the primary character ID (i.e: the one selected by the user).

    :return: Primary character ID
    :rtype: str
    """
    try:
      logging.info("正在获取角色ID...")
      # Send a GET request to the primary character endpoint.
      response = self._request_get(
        f"https://www.mixamo.com/api/v1/characters/primary",
        headers=HEADERS,
        timeout=30)
      
      if response.status_code != 200:
        logging.error(f"获取角色ID失败，状态码: {response.status_code}")
        logging.error(f"响应内容: {response.text[:500]}")
        return None

      # Get the primary character ID.
      character_id = response.json().get("primary_character_id")
      
      if character_id:
        logging.info(f"✅ 成功获取角色ID: {character_id}")
      else:
        logging.error("响应中没有找到角色ID")
        
      return character_id
      
    except requests.exceptions.Timeout:
      logging.error("❌ 获取角色ID超时（30秒）")
      return None
    except requests.exceptions.RequestException as e:
      logging.error(f"❌ 获取角色ID失败: {str(e)}")
      return None
    except Exception as e:
      logging.error(f"❌ 获取角色ID时发生未知错误: {str(e)}")
      return None

  def get_primary_character_name(self):
    """Get the primary character name (i.e: the one selected by the user).

    :return: Primary character name
    :rtype: str
    """
    try:
      logging.info("正在获取角色名称...")
      # Send a GET request to the primary character endpoint.
      response = self._request_get(
        f"https://www.mixamo.com/api/v1/characters/primary",
        headers=HEADERS,
        timeout=30)
      
      if response.status_code != 200:
        logging.error(f"获取角色名称失败，状态码: {response.status_code}")
        return None

      # Get the primary character name.
      character_name = response.json().get("primary_character_name")
      
      if character_name:
        logging.info(f"✅ 成功获取角色名称: {character_name}")
      else:
        logging.error("响应中没有找到角色名称")
        
      return character_name
      
    except requests.exceptions.Timeout:
      logging.error("❌ 获取角色名称超时（30秒）")
      return None
    except requests.exceptions.RequestException as e:
      logging.error(f"❌ 获取角色名称失败: {str(e)}")
      return None
    except Exception as e:
      logging.error(f"❌ 获取角色名称时发生未知错误: {str(e)}")
      return None

  def build_tpose_payload(self, character_id, character_name):
    """Build the payload that will be used to export the T-Pose.

    :param character_id: Primary character ID
    :type character_id: str

    :param character_name: Primary character name
    :type character name: str

    :return: Payload that will be used to export the T-Pose
    :rtype: str
    """
    # Update the 'product_name' variable so that it can be used later
    # as the FBX file name (see the 'download_animation' method).
    self.product_name = character_name

    # Build the payload.
    payload = {
      "character_id": character_id,
      "product_name": self.product_name,
      "type": "Character",
      "preferences": {"format":"fbx7_2019", "mesh":"t-pose"},
      "gms_hash": None
    }

    # Convert the payload dictionary into a JSON string.
    tpose_payload = json.dumps(payload)    

    return tpose_payload

  def get_queried_animations_data(self, query):
    """Get the ID and name of every animation found by the user query.

    :return: Queried animation IDs and names
    :rtype: dict
    """
    try:
      logging.info(f"正在搜索动画: '{query}'...")
      
      # Initialize a counter for the page number.
      page_num = 1

      # Parameters to be passed onto the endpoint.
      params = {
        "limit":96,
        "page":page_num,
        "type":"Motion",
        "query": query}

      # Send a GET request to the animations endpoint.
      # 构造带参数的 URL
      from urllib.parse import urlencode
      url_with_params = f"https://www.mixamo.com/api/v1/products?{urlencode(params)}"
      response = self._request_get(url_with_params,
        headers=HEADERS,
        timeout=30)
      
      if response.status_code != 200:
        logging.error(f"搜索动画失败，状态码: {response.status_code}")
        return {}

      data = response.json()

      # Total number of pages.
      num_pages = data.get("pagination", {}).get("num_pages", 0)
      logging.info(f"找到 {num_pages} 页结果")

      # Initialize a list to store all animations found.
      animations = []

      # Make sure we read every page and grab the animations therein.
      while page_num <= num_pages:
        try:
          params["page"] = page_num
          
          # 构造带参数的 URL
          url_with_params = f"https://www.mixamo.com/api/v1/products?{urlencode(params)}"
          response = self._request_get(url_with_params,
            headers=HEADERS,
            timeout=30)
          
          if response.status_code != 200:
            logging.warning(f"获取第 {page_num} 页失败，跳过")
            page_num += 1
            continue

          data = response.json()

          # Add animations to the list and increase the page counter by one.
          animations.extend(data.get("results", []))
          page_num += 1
          
          # Add delay between page requests
          if self.delay > 0 and page_num <= num_pages:
            time.sleep(self.delay)
            
        except requests.exceptions.Timeout:
          logging.warning(f"获取第 {page_num} 页超时，跳过")
          page_num += 1
          continue
        except Exception as e:
          logging.warning(f"获取第 {page_num} 页出错: {str(e)}")
          page_num += 1
          continue

      # Initialize a dictionary to store IDs and names.
      anim_data = {}

      # Iterate animations found by the query and add them to the dictionary. 
      for animation in animations:      
        anim_data[animation["id"]] = animation["description"]

      logging.info(f"✅ 找到 {len(anim_data)} 个匹配的动画")
      
      # Let the UI know how many animations are to be downloaded.
      self.total_tasks.emit(len(anim_data))    

      return anim_data
      
    except requests.exceptions.Timeout:
      logging.error("❌ 搜索动画超时")
      return {}
    except requests.exceptions.RequestException as e:
      logging.error(f"❌ 搜索动画失败: {str(e)}")
      return {}
    except Exception as e:
      logging.error(f"❌ 搜索动画时发生未知错误: {str(e)}")
      return {}

  def get_all_animations_data(self):
    """Get the ID and name of every animation in Mixamo.

    To speed things up, all animations have been previously exported to a
    JSON file that we'll be reading locally. This is way faster than getting
    all animations on the fly every time you run the tool.

    Mixamo doesn't seem to add new animations very often, so we're OK with
    using a pre-saved local file.

    The JSON file might be updated on GitHub if we know of any new entries.

    :return: All animation IDs and names
    :rtype: dict   
    """
    try:
      logging.info("正在加载动画列表...")
      
      # Initialize a dictionary to store all animation IDs and names.
      anim_data = {}

      # Read the local JSON file and dump its content to the dictionary.
      with open("mixamo_anims.json", "r", encoding='utf-8') as file:
        anim_data = json.load(file)

      logging.info(f"✅ 成功加载 {len(anim_data)} 个动画")
      
      # Let the UI know how many animations are to be downloaded.    
      self.total_tasks.emit(len(anim_data))
      
      return anim_data
      
    except FileNotFoundError:
      logging.error("❌ 找不到 mixamo_anims.json 文件")
      return {}
    except json.JSONDecodeError as e:
      logging.error(f"❌ JSON 文件格式错误: {str(e)}")
      return {}
    except Exception as e:
      logging.error(f"❌ 加载动画列表时发生错误: {str(e)}")
      return {}

  def build_animation_payload(self, character_id, anim_id):
    """Build the payload that will be used to export the animation.

    :param character_id: Primary character ID
    :type character_id: str

    :param anim_id: Animation ID
    :type anim_id: str

    :return: Payload that will be used to export the animation
    :rtype: str
    """
    try:
      # Send a GET request to the animation-on-character endpoint.
      response = self._request_get(
        f"https://www.mixamo.com/api/v1/products/{anim_id}?similar=0&character_id={character_id}",
        headers=HEADERS,
        timeout=30)
      
      if response.status_code != 200:
        logging.error(f"获取动画信息失败，状态码: {response.status_code}, ID: {anim_id}")
        return None

      response_json = response.json()

      # Get the animation description (make it public so that we can use it later).
      # We're using the description because some anims have the same name and this
      # would cause them to be overriden when downloading to disk.
      self.product_name = response_json.get("description", f"animation_{anim_id}")
      # Get the animation type.
      _type = response_json.get("type", "Motion")

      # Set the animation preferences.
      # NOTE: Changing the 'skin' key to True doesn't seem to have any effect.
      preferences = {
        "format": "fbx7_2019",
        "skin": False,
        "fps": "24",
        "reducekf": "0"
      }

      # Get the original 'gms_hash' property.
      gms_hash = response_json.get("details", {}).get("gms_hash")
      
      if not gms_hash:
        logging.error(f"动画没有 gms_hash 属性: {self.product_name}")
        return None

      # Read its 'params' and store their values.
      gms_hash_params = gms_hash.get("params", [])
      param_values = [int(param[-1]) for param in gms_hash_params]       

      # Build a 'params' string depending on how many params the animation has.
      # For example, if there are two params (Overdrive and Emotion), and their
      # values are 1 and 0, the string will be "1,0".
      params_string = "," .join(str(val) for val in param_values)

      # Update the 'gms_hash' properties with the ones Mixamo actually needs.
      gms_hash["params"] = params_string
      gms_hash["overdrive"] = 0

      trim_start = int(gms_hash.get("trim", [0, 100])[0])
      trim_end = int(gms_hash.get("trim", [0, 100])[1])

      gms_hash["trim"] = [trim_start, trim_end]

      # Build the payload.
      payload = {
          "character_id": character_id,
          "product_name": self.product_name,
          "type": _type,
          "preferences": preferences,
          "gms_hash": [gms_hash]
      }

      # Convert the payload dictionary into a JSON string.
      anim_payload = json.dumps(payload)

      return anim_payload
      
    except requests.exceptions.Timeout:
      logging.error(f"获取动画信息超时: ID {anim_id}")
      return None
    except requests.exceptions.RequestException as e:
      logging.error(f"获取动画信息失败: ID {anim_id}, 错误: {str(e)}")
      return None
    except (KeyError, IndexError, ValueError) as e:
      logging.error(f"解析动画数据失败: ID {anim_id}, 错误: {str(e)}")
      return None
    except Exception as e:
      logging.error(f"构建动画payload时发生未知错误: ID {anim_id}, 错误: {str(e)}")
      return None

  def export_animation(self, character_id, payload):
    """Export the animation and retrieve the download link.

    :param character_id: Primary character ID
    :type character_id: str

    :param payload: Payload that will be used to export the animation
    :type payload: str

    :return: URL to download the animation
    :rtype: str
    """
    MAX_RETRIES = 120  # 最多等待120秒（2分钟）
    retry_count = 0
    
    try:
      # Send a POST request to the export animations endpoint.
      logging.info(f"正在导出动画: {self.product_name}")
      # 对于 browser request，需要传递 JSON 数据
      import json as json_mod
      payload_dict = json_mod.loads(payload) if isinstance(payload, str) else payload
      response = self._request_post(
          f"https://www.mixamo.com/api/v1/animations/export",
          json_data=payload_dict,
          headers=HEADERS,
          timeout=30  # 30秒请求超时
      )
      
      # 202 = Accepted (异步处理中)，200 = OK
      if response.status_code == 429:
        logging.warning(f"⚠️ 触发速率限制(429)，等待 30 秒后重试...")
        time.sleep(30)
        # 重试一次
        response = self._request_post(
            f"https://www.mixamo.com/api/v1/animations/export",
            json_data=payload_dict,
            headers=HEADERS,
            timeout=30
        )
        if response.status_code == 429:
          logging.error(f"❌ 仍然是 429，跳过此动画")
          return None
      
      if response.status_code not in [200, 202]:
        logging.error(f"导出请求失败，状态码: {response.status_code}")
        return None
      
      logging.debug(f"导出请求已接受，状态码: {response.status_code}")

      # Initialize a 'status' flag.
      status = None

      # Check if the process is completed and retry if it's not.
      while status != "completed" and retry_count < MAX_RETRIES:
        # Add some delay between retries to avoid overflow.
        # Use user-specified delay or minimum 1 second
        time.sleep(max(1, self.delay))
        retry_count += 1

        try:
          # Send a GET request to the monitor endpoint.
          response = self._request_get(
              f"https://www.mixamo.com/api/v1/characters/{character_id}/monitor",
              headers=HEADERS,
              timeout=10  # 10秒超时
          )
          
          if response.status_code == 429:
            logging.warning(f"⚠️ 监控请求触发 429，等待 30 秒...")
            time.sleep(30)
            continue
          
          if response.status_code != 200:
            logging.warning(f"监控请求返回状态码: {response.status_code}, 重试 {retry_count}/{MAX_RETRIES}")
            continue

          # The loop will end as soon as the status is 'completed'.
          response_json = response.json()
          status = response_json.get("status")
          
          if status == "processing":
            if retry_count % 10 == 0:  # 每10秒记录一次
              logging.info(f"动画 {self.product_name} 处理中... ({retry_count}秒)")
          elif status == "failed":
            logging.error(f"动画 {self.product_name} 处理失败")
            return None
            
        except requests.exceptions.Timeout:
          logging.warning(f"监控请求超时，重试 {retry_count}/{MAX_RETRIES}")
          continue
        except requests.exceptions.RequestException as e:
          logging.error(f"监控请求异常: {str(e)}")
          continue
        except Exception as e:
          logging.error(f"解析响应时出错: {str(e)}")
          continue
      
      # 检查是否超时
      if retry_count >= MAX_RETRIES:
        logging.error(f"动画 {self.product_name} 处理超时（超过{MAX_RETRIES}秒），跳过")
        return None
      
      # Grab the download link from the response.
      if status == "completed":
        download_link = response.json().get("job_result")
        logging.info(f"动画 {self.product_name} 导出成功")
        return download_link
        
    except requests.exceptions.Timeout:
      logging.error(f"导出请求超时: {self.product_name}")
      return None
    except requests.exceptions.RequestException as e:
      logging.error(f"导出请求失败: {self.product_name}, 错误: {str(e)}")
      return None
    except Exception as e:
      logging.error(f"导出动画时发生未知错误: {self.product_name}, 错误: {str(e)}")
      return None
    
    return None

  def download_animation(self, url):
    """Download the animation to disk.

    :param url: URL to download the animation
    :type url: str
    """
    # Determine the file path (file existence already checked in run() before export)
    if self.path:
      if not os.path.exists(self.path):
        os.makedirs(self.path, exist_ok=True)
      file_path = f"{self.path}/{self.product_name}.fbx"
    else:
      file_path = f"{self.product_name}.fbx"
    
    # Ensure this code is only run if a URL has been retrieved.
    if url:
      try:
        # Send a GET request to the download link.
        logging.info(f"开始下载: {self.product_name}")
        result = self._download_file(url, file_path, timeout=120)  # 120秒下载超时
        
        file_size = result.get('size', 0) / 1024  # KB
        logging.info(f"✅ 下载完成: {self.product_name} ({file_size:.2f} KB)")

        # Let the UI know that a task has been completed.
        self.current_task.emit(self.task)
        # Increase the counter by one.
        self.task += 1
        
      except requests.exceptions.Timeout:
        logging.error(f"❌ 下载超时: {self.product_name}")
        # 即使失败也要更新进度
        self.current_task.emit(self.task)
        self.task += 1
      except requests.exceptions.RequestException as e:
        logging.error(f"❌ 下载失败: {self.product_name}, 错误: {str(e)}")
        self.current_task.emit(self.task)
        self.task += 1
      except IOError as e:
        logging.error(f"❌ 保存文件失败: {self.product_name}, 错误: {str(e)}")
        self.current_task.emit(self.task)
        self.task += 1
      except Exception as e:
        logging.error(f"❌ 下载时发生未知错误: {self.product_name}, 错误: {str(e)}")
        self.current_task.emit(self.task)
        self.task += 1
    else:
      logging.warning(f"⚠️  跳过下载（没有URL）: {self.product_name}")
      # 即使跳过也要更新进度
      self.current_task.emit(self.task)
      self.task += 1
