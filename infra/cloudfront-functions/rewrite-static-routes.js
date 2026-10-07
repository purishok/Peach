function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri === "/") {
    request.uri = "/index.html";
  } else if (uri.endsWith("/")) {
    request.uri = uri.slice(0, -1) + ".html";
  } else if (!uri.split("/").pop().includes(".")) {
    request.uri = uri + ".html";
  }

  return request;
}
