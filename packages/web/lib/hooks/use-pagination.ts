/**
 * usePagination — total + pageSize 算 hasNext/hasPrev/totalPages
 * 替 DataTable 之前手写的 page state + compute; 现在 DataTable 内置分页不用
 */
import { useState } from "react";
import { DEFAULT_PAGE_SIZE, ONE } from "@/const";

const FIRST_PAGE = ONE;

/** usePagination 返回的分页控制器, 含 page/hasNext/hasPrev/totalPages.
 * @client-bff */
export interface PaginationControl {
  page: number;
  setPage: (page: number) => void;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

/** usePagination — total + pageSize 算 hasNext/hasPrev/totalPages
 * @param total 总记录数
 * @param pageSize 每页大小, 默认 DEFAULT_PAGE_SIZE
 * @returns PaginationControl 分页控制器
 * @client-bff */
export const usePagination = (total: number, pageSize = DEFAULT_PAGE_SIZE): PaginationControl => {
  const [page, setPage] = useState(FIRST_PAGE);
  const totalPages = Math.max(FIRST_PAGE, Math.ceil(total / pageSize));
  return { page, setPage, totalPages, hasNext: page < totalPages, hasPrev: page > FIRST_PAGE };
};
