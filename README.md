# awesome-std-backports

# std::expected 
> `std::expected` 在低于 C++23 的 C++ 标准上的 backport / 独立实现清单。

`std::expected<T, E>` 是 C++23 标准库引入的类型，用于表示「要么持有一个成功值 `T`，要么持有一个错误值 `E`」。本清单收录把 `std::expected`（含 P2505 单子操作等相关提案）向下移植到更低 C++ 标准版本的实现。

| Repository | Minimum C++ Standard | Last Commit | Description | Notes |
| --- | --- | --- | --- | --- |
| [TartanLlama/expected](https://github.com/TartanLlama/expected) | C++11 |  | `tl::expected`，单头文件实现，附带函数式风格扩展。 | 许可证 CC0-1.0；提供 `map` / `and_then` / `or_else` 等链式操作；支持 C++11/14/17。 |
| [ibmibmibm/expected](https://github.com/ibmibmibm/expected) | C++17 |  | 待补充。 | 该仓库公开信息暂未核实，内容待补充。 |
| [nonstd-lite/expected-lite](https://github.com/nonstd-lite/expected-lite) | C++11 |  | `nonstd::expected`，单文件头文件库，基于 `std::expected` 提案实现。 | 许可证 BSL-1.0；自 0.7.0 起提供 P2505 单子操作；无第三方依赖。 |
| [zeus-cpp/expected](https://github.com/zeus-cpp/expected) | C++17 |  | `zeus::expected`，将 `std::expected` backport 到 C++17。 | 许可证 MIT；实现 P0323R12 / P2505R5 / P2549R1 及若干 LWG 修复。 |
