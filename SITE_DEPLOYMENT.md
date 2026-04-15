# 个人网站部署说明

当前仓库已经接入：

- `MkDocs` 作为静态站点生成器
- `GitHub Actions` 负责自动构建
- `GitHub Pages` 负责对外托管

## 已新增文件

- `.github/workflows/deploy-site.yml`
- `mkdocs.yml`
- `requirements-site.txt`
- `scripts/build_site.py`

## 你需要在 GitHub 上做的事

1. 把当前仓库推送到 GitHub
2. 打开仓库的 `Settings`
3. 进入 `Pages`
4. 在 `Build and deployment` 中把 `Source` 设置为 `GitHub Actions`
5. 确认默认分支是 `main` 或 `master`
6. 往默认分支再推送一次提交，或者手动执行一次 `Deploy Personal Site` 工作流

## 部署后访问地址

如果仓库名是 `algs`，并且 GitHub 用户名是 `yourname`，通常访问地址会是：

- `https://yourname.github.io/algs/`

如果你之后想绑定自定义域名，可以再补一个 `CNAME` 文件。

## 本地预览

如果你想本地预览站点，可以先安装依赖：

```bash
pip install -r requirements-site.txt
```

然后执行：

```bash
python scripts/build_site.py
mkdocs serve
```

默认会启动一个本地预览地址，方便你先检查页面效果。
