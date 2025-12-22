/// 持仓方向枚举
#[derive(PartialEq, Clone, Copy, Debug)]
pub enum Direction {
    Long,
    Short,
}

impl Direction {
    /// 获取方向符号：Long为1.0，Short为-1.0
    pub fn sign(&self) -> f64 {
        match self {
            Direction::Long => 1.0,
            Direction::Short => -1.0,
        }
    }
}
