"use client";
import { CustomEdge, CustomNode, sendEdges, sendNode } from "@/types/types";
import axios, { AxiosProgressEvent } from "axios";
import Cookies from "js-cookie";

const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_BASE_URL}`,
});

api.interceptors.request.use((config) => {
  const token = Cookies.get("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle failed token verification globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Redirect to login if token is invalid or expired
      Cookies.remove("token");
      window.location.href = "/sign-in";
    }
    return Promise.reject(error);
  }
);

export const runPythonTest = async (
  username: string,
  node: CustomNode,
  globalVariables: {
    [key: string]: string;
  }
) => {
  return api.post("/workflow/test_code", {
    username: username,
    node_id: node.id,
    name: node.data.label,
    code: node.data.code,
    pip: node.data.pip,
    image_url: node.data.imageUrl,
    global_variables: globalVariables,
  });
};

export const runConditionTest = async (
  username: string,
  node: CustomNode,
  globalVariables: {
    [key: string]: string;
  },
  conditions: {
    [key: string]: string;
  }
) => {
  return api.post("/workflow/test_condition", {
    username: username,
    name: node.data.label,
    node_id: node.id,
    conditions: conditions,
    global_variables: globalVariables,
  });
};

export const executeWorkflow = async (
  username: string,
  nodes: sendNode[],
  edges: sendEdges[],
  startNode: string,
  globalVariables: {
    [key: string]: string;
  },
  resumetTaskId: string,
  breakpoints: string[]
) => {
  return api.post("/workflow/execute", {
    username: username,
    nodes: nodes,
    edges: edges,
    start_node: startNode,
    global_variables: globalVariables,
    resume_task_id: resumetTaskId,
    breakpoints: breakpoints,
  });
};

export const deleteWorkflow = async (workflowId: string) => {
  return api.delete("/workflow/workflows/" + workflowId);
};

export const createWorkflow = async (
  workflowId: string,
  username: string,
  workflowName: string,
  workflowConfig: {},
  startNode: string,
  globalVariables: {
    [key: string]: string;
  },
  nodes: CustomNode[],
  edges: CustomEdge[]
) => {
  return api.post("/workflow/workflows", {
    workflow_id: workflowId,
    username: username,
    workflow_name: workflowName,
    workflow_config: workflowConfig,
    start_node: startNode,
    global_variables: globalVariables,
    nodes: nodes,
    edges: edges,
  });
};

export const getAllWorkflow = async (username: string) => {
  return api.get("/workflow/users/" + username + "/workflows");
};

export const renameWorkflow = async (
  workflowId: string,
  workflowName: string
) => {
  return api.post("/workflow/workflows/rename", {
    workflow_id: workflowId,
    workflow_new_name: workflowName,
  });
};

export const getWorkflowDetails = async (workflowId: string) => {
  return api.get("/workflow/workflows/" + workflowId);
};

export const getCustomNodes = async (username: string) => {
  return api.get("/workflow/nodes/" + username);
};

export const saveCustomNodes = async (
  username: string,
  customNodeName: string,
  customNode: CustomNode
) => {
  return api.post("/workflow/nodes/" + username, {
    username: username,
    custom_node_name: customNodeName,
    custom_node: customNode,
  });
};

export const deleteCustomNodes = async (
  username: string,
  custom_node_name: string
) => {
  return api.delete(`/workflow/nodes/${username}/${custom_node_name}`);
};

export const cancelWorkflow = async (username: string, taskId: string) => {
  return api.get(`/workflow/${username}/${taskId}/cancel`)
};
