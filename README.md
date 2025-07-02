# weibo-web-crawler

## Introduction

Weibo web crawler. Download images and videos from specific users.

## Usage

```
$ python weibo_web_crawler.py *path*

Args:
	*path*: Input path (a file including one user_id, start_date, and end_date per line).
```

### Input file format

```
*user_id* [*start_date*] [*end_date*] [*downdload_type*]

(If *end_date* is specific and no specific *start_date*, use '-'. If *start_date* is specific and no specific *end_date*, no other input is needed.)
(Default: Posts of all time.)
*downdload_type* can be :
    'pv' --> will download pic and vedio
    'p' --> will download pic only
    'v' --> will download vedio only
```

#### Examples

```
1234567890 2019-01-01 2019-06-01 pv
0987654321 2018-01-01 2019-01-01 p
1111111111 - 2019-02-01 v
2222222222 2019-03-01 pv # Test123
# 巫师财经
7293062537 2010-01-01 v
```

## Requirements

-   `python3`.
-   Details are in `conf/requirements.txt` 

## Get Weibo user ID

1.  Visit [https://weibo.cn](https://weibo.cn/), click ***登录*** to login.

    ![image](https://github.com/Oscarshu0719/weibo-web-crawler/blob/master/readme_img/1_new.png)
    
2.  Click ***搜索*** to search.

    ![image](https://github.com/Oscarshu0719/weibo-web-crawler/blob/master/readme_img/2_new.png)
    
3.  Enter the user you want to find and click ***找人***.

    ![image](https://github.com/Oscarshu0719/weibo-web-crawler/blob/master/readme_img/3.png)
    
4.  Enter his/her page and the `user_id` is the number string in the URL. The `user_id` is $3591355593$ in this example.

    ![image](https://github.com/Oscarshu0719/weibo-web-crawler/blob/master/readme_img/4.png)

## License

MIT License.
